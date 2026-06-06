# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Pass password manager wrapper."""

import subprocess
import sys
from typing import List, Optional, Tuple


class PassWrapper:
    """Wrapper around the pass password manager."""

    def __init__(self, store_path: str):
        """
        Initialize pass wrapper.

        Args:
            store_path: Path to the pass password store
        """
        self.store_path = store_path

    def execute(self, args: List[str]) -> Tuple[int, str, str]:
        """
        Execute a pass command.

        Args:
            args: Command arguments to pass to pass

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            import os
            # Set PASSWORD_STORE_DIR environment variable while preserving existing env
            env = os.environ.copy()
            env["PASSWORD_STORE_DIR"] = self.store_path
            
            cmd = ["pass"] + args
            
            # Check if this is an interactive command that needs stdin
            interactive_commands = {"insert", "edit", "init"}
            is_interactive = len(args) > 0 and args[0] in interactive_commands
            
            if is_interactive:
                # Allow interactive input/output for insert, edit, init commands
                result = subprocess.run(
                    cmd,
                    timeout=300,  # Longer timeout for interactive commands
                    env=env
                )
                return result.returncode, "", ""
            else:
                # Capture output for non-interactive commands
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env
                )
                return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except FileNotFoundError:
            return 127, "", "pass command not found. Please install pass."

    def is_available(self) -> bool:
        """
        Check if pass is available on the system.

        Returns:
            True if pass is installed and available
        """
        try:
            result = subprocess.run(
                ["pass", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def list_entries(self) -> List[str]:
        """
        List all password entries in the store.

        Returns:
            List of password entry names
        """
        rc, stdout, _ = self.execute(["--names-only"])
        if rc == 0:
            return [line.strip() for line in stdout.split("\n") if line.strip()]
        return []

    def get_password(self, entry: str) -> Optional[str]:
        """
        Get a password entry.

        Args:
            entry: Entry name/path

        Returns:
            Password string or None if not found
        """
        rc, stdout, _ = self.execute(["show", entry])
        if rc == 0:
            # First line is the password
            lines = stdout.split("\n")
            return lines[0] if lines else None
        return None
