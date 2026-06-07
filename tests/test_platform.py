"""Tests for platform implementations."""

import unittest
from unittest.mock import patch, MagicMock
from ppass.platform.macos import MacOSPlatform
from ppass.platform.linux import LinuxPlatform
from ppass.platform.veracrypt import VeraCryptPlatform
from ppass.platform.windows import WindowsPlatform


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
        """Test successful volume mount via diskutil (APFS device path)."""
        mock_run.return_value = MagicMock(returncode=0)
        with patch.object(self.platform, "is_mounted", return_value=False), \
             patch.object(self.platform, "get_device_identifier", return_value="disk2"):
            self.assertTrue(self.platform.mount())

    @patch("subprocess.run")
    def test_unmount_success(self, mock_run):
        """Test successful volume unmount."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        self.assertTrue(self.platform.unmount())

    def test_mount_errors_without_image_path(self):
        """mount() returns False and prints an error when no image path is set."""
        import io
        with patch.object(self.platform, "is_mounted", return_value=False), \
             patch.object(self.platform, "get_device_identifier", return_value=None), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            result = self.platform.mount()
        self.assertFalse(result)
        self.assertIn("IMAGE_PATH", mock_out.getvalue())

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

    def test_mount_raises_not_implemented(self):
        """LinuxPlatform.mount() raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.platform.mount()


class TestVeraCryptPlatform(unittest.TestCase):
    """Tests for the shared VeraCrypt backend (macOS + Linux)."""

    def setUp(self):
        self.platform = VeraCryptPlatform(
            "/mnt/vc", image_path="/tmp/test.vc", veracrypt_path="veracrypt"
        )

    @patch("subprocess.run")
    def test_is_mounted_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="1: /tmp/test.vc /mnt/vc\n")
        self.assertTrue(self.platform.is_mounted())

    @patch("subprocess.run")
    def test_is_mounted_false_empty_output(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        self.assertFalse(self.platform.is_mounted())

    @patch("subprocess.run")
    def test_is_mounted_no_false_positive_on_path_prefix(self, mock_run):
        """A volume mounted at /mnt/vc2 must not match a check for /mnt/vc."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="1: /tmp/other.vc /mnt/vc2\n"
        )
        self.assertFalse(self.platform.is_mounted())

    @patch("subprocess.run")
    def test_is_mounted_veracrypt_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        self.assertFalse(self.platform.is_mounted())

    @patch("subprocess.run")
    @patch("getpass.getpass", return_value="secret")
    @patch("os.makedirs")
    def test_mount_success(self, _makedirs, _getpass, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # is_mounted → False
            MagicMock(returncode=0),             # veracrypt attach
        ]
        self.assertTrue(self.platform.mount())

    @patch("subprocess.run")
    def test_mount_skips_when_already_mounted(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="1: /tmp/test.vc /mnt/vc\n")
        self.assertTrue(self.platform.mount())
        self.assertEqual(mock_run.call_count, 1)  # only the is_mounted check

    def test_mount_missing_image_path(self):
        p = VeraCryptPlatform("/mnt/vc")
        with patch.object(p, "is_mounted", return_value=False):
            self.assertFalse(p.mount())

    @patch("getpass.getpass", side_effect=KeyboardInterrupt)
    def test_mount_keyboard_interrupt(self, _getpass):
        with patch.object(self.platform, "is_mounted", return_value=False):
            self.assertFalse(self.platform.mount())

    @patch("getpass.getpass", side_effect=EOFError)
    def test_mount_eof(self, _getpass):
        with patch.object(self.platform, "is_mounted", return_value=False):
            self.assertFalse(self.platform.mount())

    @patch("subprocess.run")
    def test_unmount_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(self.platform.unmount())
        cmd = mock_run.call_args[0][0]
        self.assertIn("--dismount", cmd)
        self.assertIn("/mnt/vc", cmd)

    @patch("subprocess.run")
    def test_unmount_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        self.assertFalse(self.platform.unmount())

    @patch("subprocess.run")
    def test_unmount_veracrypt_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        self.assertFalse(self.platform.unmount())

    @patch("subprocess.run")
    def test_get_device_identifier(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="3: /tmp/test.vc /mnt/vc ext4\n"
        )
        self.assertEqual(self.platform.get_device_identifier(), "3")

    @patch("subprocess.run")
    def test_get_device_identifier_not_mounted(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        self.assertIsNone(self.platform.get_device_identifier())

    @patch("subprocess.run")
    def test_get_device_identifier_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        self.assertIsNone(self.platform.get_device_identifier())

    @patch("subprocess.run")
    def test_get_device_identifier_no_false_positive_on_path_prefix(self, mock_run):
        """A volume at /mnt/vc2 must not match a check for /mnt/vc."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="3: /tmp/other.vc /mnt/vc2 ext4\n"
        )
        self.assertIsNone(self.platform.get_device_identifier())

    @patch("subprocess.run")
    @patch("getpass.getpass", return_value="wrongpass")
    def test_mount_removes_created_dir_on_failure(self, _getpass, mock_run):
        """An empty mount dir ppass created is removed when authentication fails."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),         # is_mounted → False
            MagicMock(returncode=1, stderr=""),          # attach fails
        ]
        with patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("os.rmdir") as mock_rmdir, \
             patch("sys.stdout"):
            result = self.platform.mount()
        self.assertFalse(result)
        mock_rmdir.assert_called_once_with(self.platform.volume_path)

    @patch("subprocess.run")
    @patch("getpass.getpass", return_value="wrongpass")
    @patch("os.makedirs")
    def test_mount_prints_stderr_on_failure(self, _makedirs, _getpass, mock_run):
        """A failed mount forwards VeraCrypt's error message to stdout."""
        import io
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),                          # is_mounted → False
            MagicMock(returncode=1, stderr="Error: wrong password\n"),  # attach fails
        ]
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            result = self.platform.mount()
        self.assertFalse(result)
        self.assertIn("wrong password", mock_out.getvalue())


class TestWindowsPlatform(unittest.TestCase):
    """Windows stubs raise NotImplementedError on every method."""

    def setUp(self):
        self.platform = WindowsPlatform("V:")

    def test_is_mounted_raises(self):
        with self.assertRaises(NotImplementedError):
            self.platform.is_mounted()

    def test_mount_raises(self):
        with self.assertRaises(NotImplementedError):
            self.platform.mount()

    def test_unmount_raises(self):
        with self.assertRaises(NotImplementedError):
            self.platform.unmount()

    def test_get_device_identifier_raises(self):
        with self.assertRaises(NotImplementedError):
            self.platform.get_device_identifier()


if __name__ == "__main__":
    unittest.main()
