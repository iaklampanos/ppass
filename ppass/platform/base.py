# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Abstract base class for platform-specific volume operations."""

from abc import ABC, abstractmethod
from typing import Optional


class BasePlatform(ABC):
    """Abstract base class for platform-specific volume management."""

    def __init__(
        self,
        volume_path: str,
        image_path: Optional[str] = None,
        show_in_finder: bool = True,
    ):
        """
        Initialize platform handler.

        Args:
            volume_path: Path to the encrypted volume mount point
            image_path: Path to the encrypted volume image file (for mounting)
            show_in_finder: Whether the mounted volume should be browsable in
                the OS file manager (Finder on macOS). When False, the volume is
                mounted hidden to minimize exposure.
        """
        self.volume_path = volume_path
        self.image_path = image_path
        self.show_in_finder = show_in_finder

    @abstractmethod
    def is_mounted(self) -> bool:
        """
        Check if the volume is currently mounted.

        Returns:
            True if mounted, False otherwise
        """
        pass

    @abstractmethod
    def mount(self) -> bool:
        """
        Mount the encrypted volume.

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def unmount(self) -> bool:
        """
        Unmount the encrypted volume.

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_device_identifier(self) -> Optional[str]:
        """
        Get the device identifier for the volume.

        Returns:
            Device identifier string or None if not found
        """
        pass
