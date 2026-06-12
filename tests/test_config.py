"""Tests for configuration management."""

import os
import tempfile
import unittest
from ppass.config import Config, load_config, save_config


class TestConfig(unittest.TestCase):
    """Test cases for configuration management."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "config.yml")

    def tearDown(self):
        """Clean up after tests."""
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        os.rmdir(self.temp_dir)

    def test_config_defaults(self):
        """Test default configuration values."""
        config = Config(volume_path="/Volumes/Test")
        
        self.assertEqual(config.volume_path, "/Volumes/Test")
        self.assertEqual(config.store_path, ".password-store")
        self.assertEqual(config.unmount_timeout, 300)
        self.assertEqual(config.max_retries, 3)
        self.assertTrue(config.auto_unmount)

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        original_config = Config(
            volume_path="/Volumes/PasswordVault",
            store_path="passwords",
            unmount_timeout=600,
            max_retries=5,
            auto_unmount=False,
        )
        
        save_config(original_config, self.config_path)
        loaded_config = load_config(self.config_path)
        
        self.assertEqual(loaded_config.volume_path, original_config.volume_path)
        self.assertEqual(loaded_config.store_path, original_config.store_path)
        self.assertEqual(loaded_config.unmount_timeout, original_config.unmount_timeout)
        self.assertEqual(loaded_config.max_retries, original_config.max_retries)
        self.assertEqual(loaded_config.auto_unmount, original_config.auto_unmount)
        
        # Verify file permissions are restrictive
        file_stat = os.stat(self.config_path)
        file_mode = file_stat.st_mode & 0o777
        self.assertEqual(file_mode, 0o600)

    def test_load_nonexistent_config(self):
        """Test loading nonexistent config file uses defaults."""
        nonexistent_path = os.path.join(self.temp_dir, "nonexistent.yml")
        config = load_config(nonexistent_path)

        self.assertEqual(config.volume_path, "")
        self.assertEqual(config.store_path, ".password-store")

    def test_load_config_expands_tilde_in_paths(self):
        """~/... in VOLUME_PATH, IMAGE_PATH, and VERACRYPT_PATH is expanded at load time."""
        with open(self.config_path, "w") as f:
            f.write("VOLUME_PATH=~/mnt/vc\nIMAGE_PATH=~/cloud/store.vc\n")
        config = load_config(self.config_path)
        home = os.path.expanduser("~")
        self.assertEqual(config.volume_path, f"{home}/mnt/vc")
        self.assertEqual(config.image_path, f"{home}/cloud/store.vc")
        self.assertFalse(config.volume_path.startswith("~"))
        self.assertFalse(config.image_path.startswith("~"))

    def test_config_volume_backend_defaults(self):
        """volume_backend defaults to empty string; veracrypt_path to 'veracrypt'."""
        config = Config(volume_path="/Volumes/Test")
        self.assertEqual(config.volume_backend, "")
        self.assertEqual(config.veracrypt_path, "veracrypt")

    def test_save_and_load_veracrypt_config(self):
        """volume_backend and veracrypt_path round-trip through save/load."""
        config = Config(
            volume_path="/mnt/vc",
            image_path="/cloud/store.vc",
            volume_backend="veracrypt",
            veracrypt_path="/usr/local/bin/veracrypt",
        )
        save_config(config, self.config_path)
        loaded = load_config(self.config_path)
        self.assertEqual(loaded.volume_backend, "veracrypt")
        self.assertEqual(loaded.veracrypt_path, "/usr/local/bin/veracrypt")
        self.assertEqual(loaded.image_path, "/cloud/store.vc")


    def test_load_warns_on_insecure_permissions(self):
        """A group/other-accessible config file triggers a stderr warning."""
        import io
        from unittest.mock import patch
        with open(self.config_path, "w") as f:
            f.write("VOLUME_PATH=/Volumes/Test\n")
        os.chmod(self.config_path, 0o644)
        with patch("sys.stderr", new_callable=io.StringIO) as err:
            load_config(self.config_path)
        self.assertIn("accessible to other users", err.getvalue())

    def test_load_no_warning_for_0600_config(self):
        """A correctly-permissioned (0o600) config produces no warning."""
        import io
        from unittest.mock import patch
        with open(self.config_path, "w") as f:
            f.write("VOLUME_PATH=/Volumes/Test\n")
        os.chmod(self.config_path, 0o600)
        with patch("sys.stderr", new_callable=io.StringIO) as err:
            load_config(self.config_path)
        self.assertEqual(err.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
