# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""macOS-specific volume management implementation."""

import subprocess
import re
from typing import Optional
from ppass.platform.base import BasePlatform


class MacOSPlatform(BasePlatform):
    """macOS implementation of volume management using diskutil and hdiutil."""

    def __init__(
        self,
        volume_path: str,
        image_path: Optional[str] = None,
        show_in_finder: bool = True,
    ):
        """Initialize macOS platform handler.

        Args:
            volume_path: Mount point for the volume
            image_path: Path to the encrypted image file
            show_in_finder: Whether the volume should appear in Finder
        """
        import os
        super().__init__(volume_path, image_path, show_in_finder)
        # Expand user path if provided
        if self.image_path:
            self.image_path = os.path.expanduser(self.image_path)

    def is_mounted(self) -> bool:
        """
        Check if the volume is currently mounted on macOS.

        Returns:
            True if mounted, False otherwise
        """
        try:
            result = subprocess.run(
                ["diskutil", "info", self.volume_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def mount(self) -> bool:
        """
        Mount the encrypted volume on macOS.

        Supports APFS encrypted volumes and disk images (.dmg/.sparsebundle).

        Returns:
            True if successful, False otherwise
        """
        try:
            # First check if it's already mounted
            if self.is_mounted():
                return True

            # Try to mount an encrypted APFS volume
            device = self.get_device_identifier()
            if device:
                result = subprocess.run(
                    ["diskutil", "mount", device],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10
                )
                return result.returncode == 0

            # Try as a disk image mount (allow interactive password input)
            # Use image_path if available, otherwise try volume_path
            mount_source = self.image_path or self.volume_path
            cmd = ["hdiutil", "attach", mount_source]
            # -nobrowse hides the volume from Finder/Desktop. Only pass it when
            # the user has opted out of Finder visibility.
            if not self.show_in_finder:
                cmd.append("-nobrowse")
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30
            )
            return result.returncode == 0

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"Mount error: {e}")
            return False

    def unmount(self) -> bool:
        """
        Unmount the encrypted volume on macOS.

        Returns:
            True if successful, False otherwise
        """
        try:
            result = subprocess.run(
                ["diskutil", "unmount", self.volume_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_device_identifier(self) -> Optional[str]:
        """
        Get the device identifier for the volume on macOS.

        Returns:
            Device identifier (e.g., 'disk3') or None if not found
        """
        try:
            # List mounted filesystems; the mount point is the final column
            # and the device identifier is the first column.
            result = subprocess.run(
                ["df", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )

            for line in result.stdout.split("\n")[1:]:  # skip the header row
                parts = line.split()
                # Match the mount point exactly so that "/Volumes/Test" does
                # not false-match "/Volumes/TestBackup".
                if len(parts) >= 2 and parts[-1] == self.volume_path:
                    return parts[0]

            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
