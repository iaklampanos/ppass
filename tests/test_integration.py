# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""
Integration tests for the full ppass mount/unmount lifecycle.

The veracrypt binary is replaced with a stateful mock that:
  - tracks whether the container is "mounted"
  - on mount: creates the store directory tree inside the mountpoint
  - on unmount: marks as unmounted but leaves files in place, simulating
    the persistence that an encrypted container provides

All filesystem operations (mkdir, open, read) are real. No external tools
(veracrypt, pass, gpg) are required.
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from ppass.core.pass_wrapper import PassWrapper
from ppass.core.volume import VolumeManager
from ppass.watcher import spawn_watcher


class TestVeraCryptLifecycle(unittest.TestCase):
    """End-to-end lifecycle: mount → use → unmount → remount → verify."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.image_path = os.path.join(self.tmp, "vault.vc")
        self.mountpoint = os.path.join(self.tmp, "mnt")
        self.store_relpath = ".password-store"
        open(self.image_path, "w").close()  # placeholder container file

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _vc_mock(self):
        """Return a stateful subprocess.run side-effect simulating VeraCrypt.

        Mount state is tracked in a closure. On attach, the store directory
        is created; on dismount, state is flipped but files are left on disk
        (matching real VeraCrypt behaviour: the container retains its data).
        """
        mounted = [False]

        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "--list" in cmd:
                if mounted[0]:
                    return MagicMock(
                        returncode=0,
                        stdout=f"1: {self.image_path} {self.mountpoint}\n",
                    )
                return MagicMock(returncode=0, stdout="")
            if "--dismount" in cmd:
                mounted[0] = False
                return MagicMock(returncode=0)
            # attach
            mounted[0] = True
            os.makedirs(
                os.path.join(self.mountpoint, self.store_relpath), exist_ok=True
            )
            return MagicMock(returncode=0)

        return side_effect

    def _make_vm(self):
        return VolumeManager(
            volume_path=self.mountpoint,
            image_path=self.image_path,
            volume_backend="veracrypt",
            auto_unmount=False,  # no background watcher in tests
        )

    # ------------------------------------------------------------------

    @patch("getpass.getpass", return_value="test-passphrase")
    @patch("subprocess.run")
    @patch("os.path.ismount", return_value=True)
    def test_mount_state_tracks_correctly(self, mock_ismount, mock_run, _getpass):
        """VolumeManager correctly tracks mounted/unmounted state across cycles."""
        mock_run.side_effect = self._vc_mock()
        vm = self._make_vm()

        self.assertFalse(vm.is_mounted())
        self.assertTrue(vm.mount())
        self.assertTrue(vm.is_mounted())
        self.assertTrue(vm.unmount())
        self.assertFalse(vm.is_mounted())
        self.assertTrue(vm.mount())
        self.assertTrue(vm.is_mounted())

    @patch("getpass.getpass", return_value="test-passphrase")
    @patch("subprocess.run")
    @patch("os.path.ismount", return_value=True)
    def test_secret_persists_across_unmount_remount(self, mock_ismount, mock_run, _getpass):
        """A secret written after mount survives unmount and remount.

        Lifecycle: mount → write secret → unmount → remount → read back.
        """
        mock_run.side_effect = self._vc_mock()
        vm = self._make_vm()
        self.assertTrue(vm.mount())

        store = os.path.join(self.mountpoint, self.store_relpath)
        category_dir = os.path.join(store, "email")
        os.makedirs(category_dir, exist_ok=True)
        secret_file = os.path.join(category_dir, "personal.gpg")
        secret = "correct-horse-battery-staple"

        # Write (simulates `pass insert email/personal`)
        with open(secret_file, "w") as f:
            f.write(secret)

        # Unmount
        self.assertTrue(vm.unmount())
        self.assertFalse(vm.is_mounted())

        # Remount
        self.assertTrue(vm.mount())
        self.assertTrue(vm.is_mounted())

        # Read back (simulates `pass show email/personal`)
        self.assertTrue(os.path.exists(secret_file), "secret missing after remount")
        with open(secret_file) as f:
            self.assertEqual(f.read(), secret)

    @patch("getpass.getpass", return_value="test-passphrase")
    @patch("subprocess.run")
    def test_multiple_categories_persist(self, mock_run, _getpass):
        """Secrets in multiple categories all survive unmount and remount.

        Writes email/personal, email/work, and banking/savings, then
        verifies all three are present and unchanged after a remount.
        """
        mock_run.side_effect = self._vc_mock()
        vm = self._make_vm()
        self.assertTrue(vm.mount())

        store = os.path.join(self.mountpoint, self.store_relpath)
        secrets = {
            "email/personal.gpg":  "hunter2",
            "email/work.gpg":      "c0rr3ct-H0rs3",
            "banking/savings.gpg": "Tr0ub4dor&3",
        }
        for rel, val in secrets.items():
            path = os.path.join(store, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(val)

        self.assertTrue(vm.unmount())
        self.assertTrue(vm.mount())

        for rel, expected in secrets.items():
            path = os.path.join(store, rel)
            self.assertTrue(os.path.exists(path), f"missing after remount: {rel}")
            with open(path) as f:
                self.assertEqual(f.read(), expected, f"wrong value for {rel}")

    @patch("getpass.getpass", return_value="test-passphrase")
    @patch("subprocess.run")
    def test_pass_wrapper_uses_store_inside_volume(self, mock_run, _getpass):
        """PassWrapper sets PASSWORD_STORE_DIR to the path inside the volume.

        Verifies that the store path is correctly assembled and passed to
        the pass CLI via the environment, regardless of where the volume
        is mounted.
        """
        mock_run.side_effect = self._vc_mock()
        vm = self._make_vm()
        self.assertTrue(vm.mount())

        store_path = os.path.join(self.mountpoint, self.store_relpath)
        pw = PassWrapper(store_path)

        captured_env = []

        def capture(*args, **kwargs):
            captured_env.append(kwargs.get("env", {}))
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = capture
        pw.execute(["ls"])

        self.assertTrue(captured_env, "pass was never invoked")
        self.assertEqual(
            captured_env[0].get("PASSWORD_STORE_DIR"),
            store_path,
            "PASSWORD_STORE_DIR must point to the store inside the mounted volume",
        )


class TestSpawnWatcherArgs(unittest.TestCase):
    """Verify that spawn_watcher forwards backend config to the child process."""

    @patch("ppass.watcher.is_watcher_running", return_value=False)
    @patch("ppass.watcher.subprocess.Popen")
    def test_veracrypt_backend_forwarded(self, mock_popen, _running):
        """spawn_watcher must pass --backend and --veracrypt-path to the child."""
        mock_popen.return_value = MagicMock()
        spawn_watcher(
            volume_path="/mnt/vc",
            image_path="/tmp/vault.vc",
            timeout=300,
            volume_backend="veracrypt",
            veracrypt_path="/usr/local/bin/veracrypt",
        )
        self.assertTrue(mock_popen.called)
        cmd = mock_popen.call_args[0][0]
        self.assertIn("--backend", cmd)
        self.assertEqual(cmd[cmd.index("--backend") + 1], "veracrypt")
        self.assertIn("--veracrypt-path", cmd)
        self.assertEqual(cmd[cmd.index("--veracrypt-path") + 1], "/usr/local/bin/veracrypt")

    @patch("ppass.watcher.is_watcher_running", return_value=False)
    @patch("ppass.watcher.subprocess.Popen")
    def test_default_backend_forwarded(self, mock_popen, _running):
        """spawn_watcher passes empty backend for the hdiutil default path."""
        mock_popen.return_value = MagicMock()
        spawn_watcher("/mnt/vol", "/tmp/vol.dmg", 60)
        cmd = mock_popen.call_args[0][0]
        self.assertIn("--backend", cmd)
        self.assertEqual(cmd[cmd.index("--backend") + 1], "")

    def test_run_uses_backend_for_veracrypt(self):
        """watcher.run() must create VolumeManager with the correct backend.

        On Linux, VolumeManager without volume_backend='veracrypt' raises
        RuntimeError, so an import-time failure here means the fix is missing.
        """
        from ppass import watcher as w
        captured = {}

        class _FakeVM:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def is_mounted(self):
                return False

        with patch.object(w, "VolumeManager", _FakeVM), \
             patch.object(w, "_acquire_lock", return_value=MagicMock()), \
             patch.object(w, "_watch_loop", return_value=None):
            w.run("/mnt/vc", "/tmp/vault.vc", 300, "veracrypt", "/usr/bin/veracrypt")

        self.assertEqual(captured.get("volume_backend"), "veracrypt")
        self.assertEqual(captured.get("veracrypt_path"), "/usr/bin/veracrypt")
