# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Linux implementation of volume management (placeholder for future development)."""

import subprocess
from typing import Optional
from ppass.platform.base import BasePlatform
from ppass.core.runtime import secure_env


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
        super().__init__(volume_path, image_path, show_in_finder)

    def is_mounted(self) -> bool:
        """
        Check if the volume is currently mounted on Linux.

        Returns:
            True if mounted, False otherwise
        """
        try:
            result = subprocess.run(
                ["mountpoint", "-q", self.volume_path],
                timeout=5,
                env=secure_env(),
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def mount(self) -> bool:
        raise NotImplementedError(
            "LinuxPlatform does not support mounting encrypted volumes. "
            "Set VOLUME_BACKEND=veracrypt in ~/.ppassrc."
        )

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
                timeout=10,
                env=secure_env(),
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
                timeout=5,
                env=secure_env(),
            )
            
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                if parts:
                    return parts[0]
            
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
