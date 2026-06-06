"""Tests for volume manager."""

import threading
import unittest
from unittest.mock import patch, MagicMock
from ppass.core.volume import VolumeManager


class TestVolumeManager(unittest.TestCase):
    """Test cases for VolumeManager."""

    @patch("ppass.core.volume.platform.system")
    def setUp(self, mock_system):
        """Set up test fixtures."""
        mock_system.return_value = "Darwin"
        self.vm = VolumeManager("/Volumes/TestVolume", inactivity_timeout=10)

    def test_initialization(self):
        """Test volume manager initialization."""
        self.assertEqual(self.vm.volume_path, "/Volumes/TestVolume")
        self.assertEqual(self.vm.inactivity_timeout, 10)
        self.assertTrue(self.vm.auto_unmount)

    @patch("ppass.core.volume.platform.system")
    def test_platform_selection_macos(self, mock_system):
        """Test macOS platform selection."""
        mock_system.return_value = "Darwin"
        vm = VolumeManager("/Volumes/Test")
        
        self.assertIsNotNone(vm.platform)
        self.assertEqual(vm.platform.volume_path, "/Volumes/Test")

    @patch("ppass.core.volume.platform.system")
    def test_platform_selection_linux(self, mock_system):
        """Test Linux platform selection."""
        mock_system.return_value = "Linux"
        vm = VolumeManager("/mnt/test")
        
        self.assertIsNotNone(vm.platform)

    @patch("ppass.core.volume.platform.system")
    def test_platform_unsupported(self, mock_system):
        """Test unsupported platform raises error."""
        mock_system.return_value = "Windows"
        
        with self.assertRaises(RuntimeError):
            VolumeManager("/path/to/volume")

    def test_ensure_mounted(self):
        """Test ensure_mounted method."""
        with patch.object(self.vm, "is_mounted", return_value=True):
            with patch.object(self.vm.activity_tracker, "record_activity"):
                self.assertTrue(self.vm.ensure_mounted())

    @patch("ppass.core.volume.platform.system")
    def test_inactivity_timeout_unmounts_without_deadlock(self, mock_system):
        """Auto-unmount fires through the real callback chain without hanging.

        Regression test for two bugs in the inactivity path:
          1. _timeout_monitor invoked on_timeout() while holding the tracker
             lock; the unmount callback re-acquires that lock via stop(),
             deadlocking the monitor thread on a non-reentrant lock.
          2. stop(), reached from the monitor thread via the callback, tried to
             join the monitor thread on itself.
        If either regresses, the volume never unmounts and this test times out.
        """
        mock_system.return_value = "Darwin"
        vm = VolumeManager("/Volumes/TimeoutVolume", inactivity_timeout=0)

        unmounted = threading.Event()
        # Pretend the volume is mounted so _on_inactivity_timeout calls unmount,
        # and capture the real platform-level unmount call.
        vm.is_mounted = MagicMock(return_value=True)
        vm.platform.unmount = MagicMock(side_effect=lambda: unmounted.set() or True)

        vm.activity_tracker.start()
        try:
            self.assertTrue(
                unmounted.wait(timeout=5),
                "auto-unmount did not complete — the timeout path is deadlocked",
            )
        finally:
            vm.cleanup()


if __name__ == "__main__":
    unittest.main()
