# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Detached inactivity-unmount watcher for ppass.

ppass is a one-shot CLI: it runs a single ``pass`` command and exits, so it
cannot itself wait out the inactivity timeout. Instead, when a volume is
mounted, ppass spawns this module as a *detached* background process. The
watcher polls the persisted activity timestamp and unmounts the volume once it
has been idle for ``timeout`` seconds (or exits early if the volume is
unmounted by other means).

Only one watcher runs per volume, guarded by an exclusive ``flock`` on a
per-volume lockfile in the temp dir. The lock is held on an open file
descriptor for the watcher's whole lifetime, so the kernel releases it
automatically when the watcher exits -- even on SIGKILL. This makes the guard
immune to PID reuse and to races between concurrent ppass invocations: if two
watchers are spawned at once, only the one that wins the lock keeps running; the
other exits immediately. Other ppass invocations simply update the activity
file; the running watcher picks up the new timestamp on its next poll and
extends the deadline.

Run directly via:  python -m ppass.watcher --volume <path> [--image <img>] --timeout <secs>
"""

import argparse
import fcntl
import hashlib
import os
import subprocess
import sys
import time
from typing import IO, Optional

from ppass.core.runtime import runtime_dir, secure_env
from ppass.core.volume import VolumeManager

# How often (seconds) to re-check activity / mount state. Kept small enough to
# stay responsive to external unmounts without busy-spinning.
_POLL_INTERVAL = 5.0

# Unmount can transiently fail (volume busy: an open file, Spotlight indexing).
# Retry a few times before deferring to the next poll cycle.
_UNMOUNT_ATTEMPTS = 3
_UNMOUNT_BACKOFF = 2.0


def _volume_key(volume_path: str) -> str:
    """Stable short id for a volume, matching ActivityTracker's scheme."""
    return hashlib.md5(volume_path.encode(), usedforsecurity=False).hexdigest()[:8]


def _lockfile_path(volume_path: str) -> str:
    """Path to the per-volume watcher lockfile."""
    return os.path.join(runtime_dir(), f".ppass_{_volume_key(volume_path)}_watcher.lock")


def _acquire_lock(volume_path: str) -> Optional[IO]:
    """Acquire the exclusive per-volume watcher lock.

    Returns the held file object on success (keep it open to hold the lock), or
    None if another live watcher already holds it. The lock is released
    automatically when the returned object is closed or the process exits.
    """
    # O_NOFOLLOW: never follow a symlink planted at the predictable lock path.
    try:
        fd = os.open(
            _lockfile_path(volume_path),
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
        )
    except OSError:
        return None
    f = os.fdopen(fd, "r+")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


def is_watcher_running(volume_path: str) -> bool:
    """Return True if a live watcher currently holds the lock for this volume."""
    f = _acquire_lock(volume_path)
    if f is None:
        return True
    # We only probed; release immediately so a real watcher can take it.
    f.close()
    return False


def spawn_watcher(
    volume_path: str,
    image_path: str,
    timeout: int,
    volume_backend: str = "",
    veracrypt_path: str = "veracrypt",
) -> bool:
    """Spawn a detached unmount watcher for the volume, if one isn't running.

    Returns True if a watcher was spawned, False if one was already running
    (or spawning failed). The spawned child re-checks the lock itself, so even
    if this races with another invocation only one watcher survives.
    """
    if is_watcher_running(volume_path):
        return False

    cmd = [
        sys.executable,
        "-m",
        "ppass.watcher",
        "--volume",
        volume_path,
        "--image",
        image_path or "",
        "--timeout",
        str(timeout),
        "--backend",
        volume_backend or "",
        "--veracrypt-path",
        veracrypt_path or "veracrypt",
    ]
    log_path = os.path.join(
        runtime_dir(),
        f".ppass_{_volume_key(volume_path)}_watcher.log",
    )
    try:
        # O_NOFOLLOW (no symlink following), 0o600 (owner-only), and O_TRUNC so
        # the log starts fresh for each watcher session and cannot grow without
        # bound across restarts. Only one watcher runs per volume, so truncating
        # here never discards a live watcher's output.
        log_fd = os.open(
            log_path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
            0o600,
        )
        log_file = os.fdopen(log_fd, "w")
        try:
            subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=log_file,
                start_new_session=True,  # detach from the ppass CLI's session
                env=secure_env(),        # sanitized PATH for binary resolution
            )
        finally:
            log_file.close()  # parent closes its copy; child keeps its own fd
    except OSError:
        return False
    return True


def _try_unmount(
    vm: VolumeManager,
    attempts: int = _UNMOUNT_ATTEMPTS,
    backoff: float = _UNMOUNT_BACKOFF,
) -> bool:
    """Attempt to unmount, retrying a few times. Returns True on success."""
    for attempt in range(attempts):
        if vm.unmount():
            return True
        if attempt < attempts - 1:
            time.sleep(backoff)
    return False


def _watch_loop(vm: VolumeManager, poll_interval: float = _POLL_INTERVAL) -> None:
    """Block until the volume goes idle past its timeout, then unmount it.

    Returns early (without unmounting) if the volume is already unmounted. If an
    unmount attempt fails because the volume is busy, keeps watching and retries
    on the next cycle rather than giving up.
    """
    while True:
        if not vm.is_mounted():
            return  # unmounted externally; nothing to do

        # Observe activity recorded by other ppass invocations.
        vm.activity_tracker.reload_last_activity()
        remaining = vm.activity_tracker.get_remaining_time()

        if remaining <= 0:
            if _try_unmount(vm):
                return
            # Idle but busy: wait a full cycle, then try again. Any new activity
            # (reloaded above) will push remaining back above zero.
            time.sleep(poll_interval)
            continue

        time.sleep(max(0.5, min(remaining, poll_interval)))


def run(
    volume_path: str,
    image_path: str,
    timeout: int,
    volume_backend: str = "",
    veracrypt_path: str = "veracrypt",
) -> int:
    """Run the watch loop for a volume under the per-volume lock."""
    lock = _acquire_lock(volume_path)
    if lock is None:
        return 0  # another watcher already owns this volume; stand down

    lock_path = _lockfile_path(volume_path)
    try:
        # auto_unmount=False: the watcher drives unmounting via its own loop and
        # must not start the (process-bound) timeout thread or re-spawn watchers.
        vm = VolumeManager(
            volume_path=volume_path,
            image_path=image_path,
            inactivity_timeout=timeout,
            auto_unmount=False,
            volume_backend=volume_backend,
            veracrypt_path=veracrypt_path,
        )
        _watch_loop(vm)
    finally:
        try:
            os.unlink(lock_path)  # unlink before releasing so no racing watcher opens it
        except OSError:
            pass
        lock.close()  # releases the flock (also released by the OS on exit)
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="ppass-watcher", description=__doc__)
    parser.add_argument("--volume", required=True, help="Volume mount point")
    parser.add_argument("--image", default="", help="Encrypted image path")
    parser.add_argument("--timeout", type=int, required=True, help="Inactivity timeout (seconds)")
    parser.add_argument("--backend", default="", help="Volume backend (veracrypt or hdiutil)")
    parser.add_argument("--veracrypt-path", default="veracrypt", help="Path to veracrypt binary")
    args = parser.parse_args(argv)
    return run(args.volume, args.image, args.timeout, args.backend, args.veracrypt_path)


if __name__ == "__main__":
    sys.exit(main())
