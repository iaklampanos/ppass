# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Linux implementation of volume management (placeholder for future development)."""

import subprocess
from typing import Optional
from ppass.platform.base import BasePlatform


class LinuxPlatform(BasePlatform):
    """Linux implementation of volume management using mount/umount."""

    def __init__(
        self,
        volume_path: str,
        image_path: Optional[str] = None,
        show_in_finder: bool = True,
    ):
        """Initialize Linux platform handler.

        Args:
            volume_path: Mount point for the volume
            image_path: Path to the encrypted image file
            show_in_finder: Accepted for API parity with macOS; Linux mounts are
                always visible to the file manager, so this is a no-op here.
        """
        import os
        super().__init__(volume_path, image_path, show_in_finder)
        # Expand user path if provided
        if self.image_path:
            self.image_path = os.path.expanduser(self.image_path)

    def is_mounted(self) -> bool:
        """
        Check if the volume is currently mounted on Linux.

        Returns:
            True if mounted, False otherwise
        """
        try:
            result = subprocess.run(
                ["mountpoint", "-q", self.volume_path],
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def mount(self) -> bool:
        """
        Mount the encrypted volume on Linux.

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.is_mounted():
                return True

            # Try standard mount
            result = subprocess.run(
                ["mount", self.volume_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def unmount(self) -> bool:
        """
        Unmount the encrypted volume on Linux.

        Returns:
            True if successful, False otherwise
        """
        try:
            result = subprocess.run(
                ["umount", self.volume_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_device_identifier(self) -> Optional[str]:
        """
        Get the device identifier for the volume on Linux.

        Returns:
            Device identifier or None if not found
        """
        try:
            result = subprocess.run(
                ["df", self.volume_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                if parts:
                    return parts[0]
            
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
