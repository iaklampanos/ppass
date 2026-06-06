#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>
#
# Run a full VeraCrypt lifecycle test inside a privileged Debian 12 Docker
# container.  Useful for verifying that the veracrypt backend works on Linux
# when the host machine cannot run VeraCrypt directly (e.g. macOS without
# macFUSE).
#
# Requirements:
#   - Docker Desktop (or Docker Engine) running
#   - Internet access (downloads VeraCrypt .deb from GitHub releases)
#
# Usage:
#   bash scripts/test_veracrypt_linux.sh
#
# The script is self-contained: it installs all dependencies inside a
# throwaway container and exits cleanly.  The host working directory is
# mounted read-only so ppass is installed from source inside the container.
#
# Docker-specific note
# --------------------
# Docker Desktop on macOS does not run udevd, so device mapper device nodes
# (/dev/mapper/veracryptN) are not created automatically when dm-crypt opens
# a mapping.  The script works around this by running `dmsetup mknodes` in a
# tight background loop during every veracrypt invocation.  On a real Linux
# machine (bare-metal or VM) udevd handles this automatically and no
# workaround is needed.

set -euo pipefail

PPASS_SRC="$(cd "$(dirname "$0")/.." && pwd)"

docker run --privileged --rm \
    -v "${PPASS_SRC}:/ppass:ro" \
    -w /ppass \
    debian:12 bash << 'CONTAINER'
set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

step() { echo ""; echo "=== $* ==="; }

# Run dmsetup mknodes in a background loop so that device mapper device nodes
# appear in /dev/mapper/ even without udevd running.  Returns the PID.
start_mknodes() {
    while true; do dmsetup mknodes 2>/dev/null; sleep 0.05; done &
    echo $!
}

stop_mknodes() {
    kill "$1" 2>/dev/null; wait "$1" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# 0. Clean up stale device mapper entries from previous (interrupted) runs
# ---------------------------------------------------------------------------
step "Cleaning up stale DM devices"
for dev in $(dmsetup ls 2>/dev/null | grep veracrypt | awk '{print $1}'); do
    echo "  removing stale: $dev"
    dmsetup remove "$dev" 2>/dev/null || true
done
echo "  DM state: $(dmsetup ls 2>/dev/null | grep -v '^No ' || echo 'clean')"

# ---------------------------------------------------------------------------
# 1. Install dependencies
# ---------------------------------------------------------------------------
step "Installing dependencies"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    libfuse2 wget python3 python3-pip dmsetup e2fsprogs 2>&1 | tail -3

# ---------------------------------------------------------------------------
# 2. Download and install VeraCrypt console package (auto-detect arch)
# ---------------------------------------------------------------------------
step "Installing VeraCrypt"
ARCH=$(dpkg --print-architecture)   # amd64 or arm64
DEB_URL=$(python3 -c "
import urllib.request, json, sys
arch = sys.argv[1]
with urllib.request.urlopen('https://api.github.com/repos/veracrypt/VeraCrypt/releases/latest') as r:
    data = json.load(r)
for a in data.get('assets', []):
    url = a.get('browser_download_url', '')
    if 'console' in url and f'Debian-12-{arch}.deb' in url and not url.endswith('.sig'):
        print(url); break
" "$ARCH")
echo "  URL: $DEB_URL"
wget -q "$DEB_URL" -O /tmp/veracrypt-console.deb
dpkg -i /tmp/veracrypt-console.deb 2>/dev/null || true
echo "  $(veracrypt --text --version)"

# ---------------------------------------------------------------------------
# 3. Install ppass from the mounted source tree
# ---------------------------------------------------------------------------
step "Installing ppass"
# Copy to a writable location because the source is mounted read-only
cp -r /ppass /tmp/ppass_src
pip install -q -e /tmp/ppass_src 2>&1 | tail -2

# ---------------------------------------------------------------------------
# 4. Create a 20 MB VeraCrypt container with ext4
# ---------------------------------------------------------------------------
step "Creating VeraCrypt container"
dd if=/dev/zero of=/tmp/vault.vc bs=1M count=25 2>/dev/null

MK_PID=$(start_mknodes)
veracrypt --text --create /tmp/vault.vc \
    --size=20971520 \
    --password=testpass123 \
    --volume-type=normal \
    --encryption=AES \
    --hash=SHA-512 \
    --filesystem=ext4 \
    --pim=0 \
    --keyfiles="" \
    --random-source=/dev/urandom \
    --non-interactive 2>&1 | grep -v "^Done\|^Speed\|^Left"
stop_mknodes "$MK_PID"
echo "  container created"

# ---------------------------------------------------------------------------
# 5. Raw VeraCrypt mount → write → unmount → remount → read
# ---------------------------------------------------------------------------
step "Raw VeraCrypt mount/unmount cycle"
mkdir -p /mnt/vc

MK_PID=$(start_mknodes)
echo "testpass123" | veracrypt --text --non-interactive --stdin /tmp/vault.vc /mnt/vc
stop_mknodes "$MK_PID"
echo "  mounted: $(veracrypt --text --list)"

echo "veracrypt-linux-ok" > /mnt/vc/probe.txt
veracrypt --text --dismount /mnt/vc
echo "  unmounted"

MK_PID=$(start_mknodes)
echo "testpass123" | veracrypt --text --non-interactive --stdin /tmp/vault.vc /mnt/vc
stop_mknodes "$MK_PID"
CONTENT=$(cat /mnt/vc/probe.txt)
[ "$CONTENT" = "veracrypt-linux-ok" ] || { echo "FAIL: unexpected content: $CONTENT"; exit 1; }
echo "  remounted, read back: $CONTENT"
veracrypt --text --dismount /mnt/vc
echo "  raw cycle: PASSED"

# ---------------------------------------------------------------------------
# 6. ppass lifecycle test via VolumeManager
# ---------------------------------------------------------------------------
step "ppass VolumeManager lifecycle test"
python3 << 'PYEOF'
import os, getpass, threading, time, subprocess

# Bypass TTY passphrase prompt (no interactive terminal in container)
getpass.getpass = lambda prompt="": "testpass123"

# Keep device nodes alive throughout the test (Docker-only workaround)
_stop = [False]
def _mknodes():
    while not _stop[0]:
        subprocess.run(["dmsetup", "mknodes"], capture_output=True)
        time.sleep(0.05)
t = threading.Thread(target=_mknodes, daemon=True); t.start()

from ppass.core.volume import VolumeManager

vm = VolumeManager(
    volume_path="/mnt/vc",
    image_path="/tmp/vault.vc",
    volume_backend="veracrypt",
    auto_unmount=False,
)

def ok(msg): print(f"  {msg}", flush=True)

assert vm.mount(),      "mount() returned False"
assert vm.is_mounted(), "is_mounted() False after mount"
ok("mount OK")

store = "/mnt/vc/.password-store"
secrets = {
    "email/personal":  "hunter2",
    "banking/savings": "Tr0ub4dor&3",
}
for path, val in secrets.items():
    full = os.path.join(store, path + ".gpg")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w").write(val)
ok(f"wrote {len(secrets)} secrets")

assert vm.unmount(),        "unmount() returned False"
assert not vm.is_mounted(), "is_mounted() True after unmount"
ok("unmount OK")

assert vm.mount(),      "remount() returned False"
assert vm.is_mounted(), "is_mounted() False after remount"
ok("remount OK")

for path, expected in secrets.items():
    full = os.path.join(store, path + ".gpg")
    got = open(full).read()
    assert got == expected, f"{path}: expected '{expected}', got '{got}'"
    ok(f"  {path}: '{got}'")

assert vm.unmount(), "final unmount() returned False"
ok("final unmount OK")

_stop[0] = True
print("")
print("ppass VeraCrypt lifecycle test on Linux: PASSED")
PYEOF

CONTAINER
