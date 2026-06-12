# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Tests for the runtime state-directory and PATH-hardening helpers."""

import os
import stat
import unittest
from unittest.mock import patch

from ppass.core import runtime


class TestSecurePath(unittest.TestCase):
    """secure_path() strips hijackable PATH entries."""

    def test_drops_empty_and_relative_entries(self):
        with patch.dict(os.environ, {"PATH": f"/usr/bin{os.pathsep}{os.pathsep}rel"}):
            entries = runtime.secure_path().split(os.pathsep)
        self.assertIn("/usr/bin", entries)
        self.assertNotIn("", entries)
        self.assertNotIn("rel", entries)

    def test_drops_world_writable_without_sticky_bit(self, ):
        # A world-writable dir without the sticky bit is a drop target.
        import tempfile
        bad = tempfile.mkdtemp()
        os.chmod(bad, 0o777)  # rwx for all, no sticky bit
        try:
            with patch.dict(os.environ, {"PATH": f"/usr/bin{os.pathsep}{bad}"}):
                entries = runtime.secure_path().split(os.pathsep)
            self.assertIn("/usr/bin", entries)
            self.assertNotIn(bad, entries)
        finally:
            os.rmdir(bad)

    def test_secure_env_overrides_path_only(self):
        with patch.dict(os.environ, {"PATH": "rel", "PPASS_MARKER": "1"}):
            env = runtime.secure_env()
        self.assertEqual(env.get("PPASS_MARKER"), "1")
        self.assertNotIn("rel", env["PATH"].split(os.pathsep))


class TestRuntimeDir(unittest.TestCase):
    """runtime_dir() yields a private, owner-only directory."""

    def test_is_private_directory(self):
        d = runtime.runtime_dir()
        info = os.lstat(d)
        self.assertTrue(stat.S_ISDIR(info.st_mode))
        # No access for group or other.
        self.assertEqual(info.st_mode & 0o077, 0)

    def test_rejects_directory_owned_by_other_user(self):
        import tempfile
        d = os.path.join(tempfile.mkdtemp(), "ppass-state")
        os.mkdir(d, 0o700)
        try:
            # Pretend the current process is a different uid than the dir owner.
            with patch("ppass.core.runtime.os.getuid", return_value=os.lstat(d).st_uid + 1):
                with self.assertRaises(RuntimeError):
                    runtime._ensure_private_dir(d)
        finally:
            os.rmdir(d)
            os.rmdir(os.path.dirname(d))


if __name__ == "__main__":
    unittest.main()
