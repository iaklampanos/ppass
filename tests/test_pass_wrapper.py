"""Tests for pass wrapper."""

import unittest
from unittest.mock import patch, MagicMock
from ppass.core.pass_wrapper import PassWrapper


class TestPassWrapper(unittest.TestCase):
    """Test cases for PassWrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.wrapper = PassWrapper("/tmp/test_store")

    @patch("subprocess.run")
    def test_execute_success(self, mock_run):
        """Test successful pass command execution."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "test_password\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        rc, stdout, stderr = self.wrapper.execute(["show", "test"])
        
        self.assertEqual(rc, 0)
        self.assertEqual(stdout, "test_password\n")
        self.assertEqual(stderr, "")

    @patch("subprocess.run")
    def test_execute_failure(self, mock_run):
        """Test failed pass command execution."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: not in a password store\n"
        mock_run.return_value = mock_result
        
        rc, stdout, stderr = self.wrapper.execute(["show", "nonexistent"])
        
        self.assertEqual(rc, 1)

    @patch("subprocess.run")
    def test_is_available(self, mock_run):
        """Test pass availability check."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        self.assertTrue(self.wrapper.is_available())

    @patch("subprocess.run")
    def test_list_entries(self, mock_run):
        """Test listing password entries."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "mail/gmail\nmail/work\nbank/account\n"
        mock_run.return_value = mock_result
        
        entries = self.wrapper.list_entries()
        
        self.assertEqual(len(entries), 3)
        self.assertIn("mail/gmail", entries)


if __name__ == "__main__":
    unittest.main()
