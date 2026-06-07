# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""VeraCrypt volume management — shared implementation for macOS and Linux.

Prerequisites:
- macOS:  ``brew install --cask veracrypt``
- Linux:  package manager or https://veracrypt.fr/en/Downloads.html

The same ``.vc`` container file can be mounted on both platforms, making
this backend suitable for volumes stored on cloud drives shared across
machines.

The ``show_in_finder`` option has no effect with this backend — VeraCrypt
volumes are always visible in the OS file manager.
"""

import getpass
import os
import subprocess
from typing import Optional

from ppass.platform.base import BasePlatform


class VeraCryptPlatform(BasePlatform):
    """Volume management via the VeraCrypt CLI (macOS and Linux)."""

    def __init__(
        self,
        volume_path: str,
        image_path: Optional[str] = None,
        show_in_finder: bool = True,
        veracrypt_path: str = "veracrypt",
    ):
        """
        Args:
            volume_path: Mount point directory (created automatically if absent).
            image_path: Path to the VeraCrypt container file.
            show_in_finder: Accepted for API parity; ignored by this backend.
            veracrypt_path: Path to the ``veracrypt`` binary.  Override when
                the binary is not on PATH (e.g. a non-standard install location).
        """
        super().__init__(volume_path, image_path, show_in_finder)
        self.veracrypt_path = os.path.expanduser(veracrypt_path)

    # ------------------------------------------------------------------
    # BasePlatform interface
    # ------------------------------------------------------------------

    def is_mounted(self) -> bool:
        """Return True if the container is currently mounted at volume_path."""
        try:
            result = subprocess.run(
                [self.veracrypt_path, "--text", "--list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return any(
                self.volume_path in line.split()
                for line in result.stdout.splitlines()
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def mount(self) -> bool:
        """Prompt for the passphrase and mount the VeraCrypt container.

        The passphrase is read via ``getpass`` (no echo; reads from /dev/tty
        so it works even when stdout/stdin are redirected) and piped to
        ``veracrypt --stdin``, keeping it out of process-list arguments.
        """
        if self.is_mounted():
            return True

        if not self.image_path:
            print("Error: IMAGE_PATH is required for the veracrypt backend.", flush=True)
            return False

        try:
            passphrase = getpass.getpass("VeraCrypt passphrase: ")
        except (EOFError, KeyboardInterrupt):
            return False

        dir_created = not os.path.exists(self.volume_path)
        try:
            os.makedirs(self.volume_path, exist_ok=True)
            result = subprocess.run(
                [
                    self.veracrypt_path,
                    "--text",
                    "--non-interactive",
                    "--stdin",
                    self.image_path,
                    self.volume_path,
                ],
                input=passphrase,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                if result.stderr:
                    print(result.stderr.strip(), flush=True)
                if dir_created:
                    try:
                        os.rmdir(self.volume_path)
                    except OSError:
                        pass
                return False
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"Mount error: {e}", flush=True)
            if dir_created:
                try:
                    os.rmdir(self.volume_path)
                except OSError:
                    pass
            return False

    def unmount(self) -> bool:
        """Dismount the VeraCrypt volume."""
        try:
            result = subprocess.run(
                [self.veracrypt_path, "--text", "--dismount", self.volume_path],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_device_identifier(self) -> Optional[str]:
        """Return the VeraCrypt slot number for this volume, or None."""
        try:
            result = subprocess.run(
                [self.veracrypt_path, "--text", "--list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.splitlines():
                if self.volume_path in line.split():
                    # Output format: "1: /path/to/container  /mountpoint  ..."
                    parts = line.split(":", 1)
                    if parts:
                        return parts[0].strip()
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
