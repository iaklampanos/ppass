"""Tests for platform implementations."""

import unittest
from unittest.mock import patch, MagicMock
from ppass.platform.macos import MacOSPlatform
from ppass.platform.linux import LinuxPlatform


class TestMacOSPlatform(unittest.TestCase):
    """Test cases for macOS platform."""

    def setUp(self):
        """Set up test fixtures."""
        self.platform = MacOSPlatform("/Volumes/TestVolume")

    @patch("subprocess.run")
    def test_is_mounted_true(self, mock_run):
        """Test is_mounted returns True when volume exists."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        self.assertTrue(self.platform.is_mounted())

    @patch("subprocess.run")
    def test_is_mounted_false(self, mock_run):
        """Test is_mounted returns False when volume doesn't exist."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        
        self.assertFalse(self.platform.is_mounted())

    @patch("subprocess.run")
    def test_mount_success(self, mock_run):
        """Test successful volume mount."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Mock is_mounted to return False first, then True
        with patch.object(self.platform, "is_mounted", side_effect=[False, True]):
            self.assertTrue(self.platform.mount())

    @patch("subprocess.run")
    def test_unmount_success(self, mock_run):
        """Test successful volume unmount."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        self.assertTrue(self.platform.unmount())

    @patch("subprocess.run")
    def test_image_mount_visible_in_finder_omits_nobrowse(self, mock_run):
        """When show_in_finder is True, the image is attached without -nobrowse."""
        mock_run.return_value = MagicMock(returncode=0)
        platform = MacOSPlatform(
            "/Volumes/Test", image_path="/tmp/img.sparsebundle", show_in_finder=True
        )
        with patch.object(platform, "is_mounted", return_value=False), \
             patch.object(platform, "get_device_identifier", return_value=None):
            self.assertTrue(platform.mount())

        hdiutil_cmd = mock_run.call_args[0][0]
        self.assertEqual(hdiutil_cmd[:2], ["hdiutil", "attach"])
        self.assertNotIn("-nobrowse", hdiutil_cmd)

    @patch("subprocess.run")
    def test_image_mount_hidden_uses_nobrowse(self, mock_run):
        """When show_in_finder is False, the image is attached with -nobrowse."""
        mock_run.return_value = MagicMock(returncode=0)
        platform = MacOSPlatform(
            "/Volumes/Test", image_path="/tmp/img.sparsebundle", show_in_finder=False
        )
        with patch.object(platform, "is_mounted", return_value=False), \
             patch.object(platform, "get_device_identifier", return_value=None):
            self.assertTrue(platform.mount())

        hdiutil_cmd = mock_run.call_args[0][0]
        self.assertIn("-nobrowse", hdiutil_cmd)


class TestLinuxPlatform(unittest.TestCase):
    """Test cases for Linux platform."""

    def setUp(self):
        """Set up test fixtures."""
        self.platform = LinuxPlatform("/mnt/testvol")

    @patch("subprocess.run")
    def test_is_mounted_true(self, mock_run):
        """Test is_mounted returns True when mounted."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        self.assertTrue(self.platform.is_mounted())

    @patch("subprocess.run")
    def test_is_mounted_false(self, mock_run):
        """Test is_mounted returns False when not mounted."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        
        self.assertFalse(self.platform.is_mounted())


if __name__ == "__main__":
    unittest.main()
