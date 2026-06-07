"""Tests for the ppass command-line interface."""

import unittest
from unittest.mock import patch, MagicMock

from ppass.cli import main
from ppass.config import Config


def _config(**overrides):
    """Build a Config with sensible test defaults."""
    base = dict(volume_path="/Volumes/TestVolume", store_path=".password-store")
    base.update(overrides)
    return Config(**base)


class TestCli(unittest.TestCase):
    """Test cases for the CLI entry point."""

    def test_missing_volume_path_errors(self):
        """Exit non-zero when no volume_path is configured."""
        with patch("ppass.cli.load_config", return_value=_config(volume_path="")):
            self.assertEqual(main([]), 1)

    @patch("ppass.cli.VolumeManager")
    def test_status_mounted(self, mock_vm_cls):
        """`ppass status` reports a mounted volume and exits 0."""
        vm = mock_vm_cls.return_value
        vm.is_mounted.return_value = True
        vm.activity_tracker.get_remaining_time.return_value = 90

        with patch("ppass.cli.load_config", return_value=_config(auto_unmount=True)):
            self.assertEqual(main(["status"]), 0)
        vm.is_mounted.assert_called_once()

    @patch("ppass.cli.VolumeManager")
    def test_mount_failure_returns_error(self, mock_vm_cls):
        """`ppass mount` returns 1 when the volume fails to mount."""
        mock_vm_cls.return_value.mount.return_value = False

        with patch("ppass.cli.load_config", return_value=_config()):
            self.assertEqual(main(["mount"]), 1)

    @patch("ppass.cli.VolumeManager")
    def test_unmount_success(self, mock_vm_cls):
        """`ppass unmount` returns 0 on success."""
        mock_vm_cls.return_value.unmount.return_value = True

        with patch("ppass.cli.load_config", return_value=_config()):
            self.assertEqual(main(["unmount"]), 0)

    @patch("ppass.cli.PassWrapper")
    @patch("ppass.cli.VolumeManager")
    def test_proxies_to_pass_after_mounting(self, mock_vm_cls, mock_pw_cls):
        """Unknown commands mount the volume and proxy through to pass."""
        vm = mock_vm_cls.return_value
        vm.ensure_mounted.return_value = True
        mock_pw_cls.return_value.execute.return_value = (0, "secret\n", "")

        with patch("ppass.cli.load_config", return_value=_config()):
            rc = main(["show", "github"])

        self.assertEqual(rc, 0)
        vm.ensure_mounted.assert_called_once()
        mock_pw_cls.return_value.execute.assert_called_once_with(["show", "github"])
        vm.cleanup.assert_called_once()

    @patch("ppass.cli.PassWrapper")
    @patch("ppass.cli.VolumeManager")
    def test_proxy_aborts_when_mount_fails(self, mock_vm_cls, mock_pw_cls):
        """If the volume can't be mounted, pass is never invoked."""
        mock_vm_cls.return_value.ensure_mounted.return_value = False

        with patch("ppass.cli.load_config", return_value=_config()):
            self.assertEqual(main(["show", "github"]), 1)
        mock_pw_cls.return_value.execute.assert_not_called()

    @patch("ppass.cli.spawn_watcher")
    @patch("ppass.cli.VolumeManager")
    def test_mount_success(self, mock_vm_cls, mock_watcher):
        """`ppass mount` returns 0 and spawns the watcher on success."""
        mock_vm_cls.return_value.mount.return_value = True

        with patch("ppass.cli.load_config", return_value=_config(auto_unmount=True)):
            self.assertEqual(main(["mount"]), 0)
        mock_watcher.assert_called_once()

    @patch("ppass.cli.VolumeManager")
    def test_unmount_failure(self, mock_vm_cls):
        """`ppass unmount` returns 1 when the platform fails to unmount."""
        mock_vm_cls.return_value.unmount.return_value = False

        with patch("ppass.cli.load_config", return_value=_config()):
            self.assertEqual(main(["unmount"]), 1)

    @patch("ppass.cli.VolumeManager")
    def test_status_not_mounted(self, mock_vm_cls):
        """`ppass status` exits 0 even when the volume is not mounted."""
        mock_vm_cls.return_value.is_mounted.return_value = False

        with patch("ppass.cli.load_config", return_value=_config()):
            self.assertEqual(main(["status"]), 0)

    @patch("ppass.cli.PassWrapper")
    @patch("ppass.cli.VolumeManager")
    def test_verbose_flag(self, mock_vm_cls, mock_pw_cls):
        """`--verbose` is accepted without error."""
        mock_vm_cls.return_value.ensure_mounted.return_value = True
        mock_pw_cls.return_value.execute.return_value = (0, "", "")

        with patch("ppass.cli.load_config", return_value=_config()):
            self.assertEqual(main(["--verbose", "show", "test"]), 0)


class TestSetup(unittest.TestCase):
    """Tests for the interactive --setup flow."""

    def test_invalid_timeout_input_keeps_default(self):
        """Non-numeric timeout input is rejected gracefully; default is kept."""
        from ppass.cli import _handle_setup
        cfg = _config(unmount_timeout=300)
        responses = iter([
            "hdiutil",  # backend
            "",         # image path
            "",         # volume path
            "",         # store path
            "notanumber",  # invalid timeout
        ])
        with patch("builtins.input", side_effect=responses), \
             patch("ppass.cli.save_config"):
            _handle_setup(cfg, None)
        self.assertEqual(cfg.unmount_timeout, 300)

    def test_valid_timeout_input_is_applied(self):
        """A numeric timeout input updates the config."""
        from ppass.cli import _handle_setup
        cfg = _config(unmount_timeout=300)
        responses = iter(["hdiutil", "", "", "", "600"])
        with patch("builtins.input", side_effect=responses), \
             patch("ppass.cli.save_config"):
            _handle_setup(cfg, None)
        self.assertEqual(cfg.unmount_timeout, 600)

    def test_setup_keyboard_interrupt_exits_cleanly(self):
        """Ctrl+C during setup prints a cancellation message and returns 1."""
        from ppass.cli import _handle_setup
        cfg = _config()
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            rc = _handle_setup(cfg, None)
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
