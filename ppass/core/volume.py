# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Volume lifecycle management."""

import os
import sys
import platform
from typing import Optional

from ppass.platform.base import BasePlatform
from ppass.platform.macos import MacOSPlatform
from ppass.platform.linux import LinuxPlatform
from ppass.platform.veracrypt import VeraCryptPlatform
from ppass.platform.windows import WindowsPlatform
from ppass.core.activity import ActivityTracker


class VolumeManager:
    """Manages encrypted volume lifecycle (mount/unmount with activity tracking)."""

    def __init__(
        self,
        volume_path: str,
        image_path: str = "",
        inactivity_timeout: int = 300,
        auto_unmount: bool = True,
        max_retries: int = 3,
        show_in_finder: bool = True,
        volume_backend: str = "",
        veracrypt_path: str = "veracrypt",
    ):
        """
        Initialize volume manager.

        Args:
            volume_path: Path to the encrypted volume mount point
            image_path: Path to the encrypted volume image file
            inactivity_timeout: Seconds before auto-unmount (default 300)
            auto_unmount: Whether to auto-unmount on inactivity
            max_retries: Number of mount attempts before giving up (default 3)
            show_in_finder: Whether the mounted volume is visible in Finder
                (hdiutil backend only)
            volume_backend: "hdiutil" (macOS default) or "veracrypt"
            veracrypt_path: Path to veracrypt binary (default: "veracrypt")
        """
        self.volume_path = volume_path
        self.image_path = image_path
        self.inactivity_timeout = inactivity_timeout
        self.auto_unmount = auto_unmount
        self.max_retries = max(1, max_retries)
        self.show_in_finder = show_in_finder
        self.volume_backend = volume_backend
        self.veracrypt_path = veracrypt_path
        
        # Initialize platform-specific handler
        self.platform = self._init_platform()
        
        # Initialize activity tracker with volume-specific tracking
        # Use volume path hash to create unique tracker ID for each volume
        import hashlib
        tracker_id = f"ppass_{hashlib.md5(volume_path.encode()).hexdigest()[:8]}"
        
        self.activity_tracker = ActivityTracker(
            inactivity_timeout=inactivity_timeout,
            on_timeout=self._on_inactivity_timeout if auto_unmount else None,
            tracker_id=tracker_id
        )
        
        # If volume is already mounted, start activity tracking
        if self.is_mounted() and auto_unmount:
            self.activity_tracker.start()

    def _init_platform(self) -> BasePlatform:
        """Initialize the appropriate platform handler based on OS and backend config.

        Backend selection:
        - "veracrypt"  → VeraCryptPlatform on any OS (cross-platform)
        - "" / "hdiutil" → MacOSPlatform on macOS; error on Linux
        - Windows      → WindowsPlatform stub (raises NotImplementedError)

        Raises:
            RuntimeError: If the platform/backend combination is unsupported.
        """
        system = platform.system()
        backend = self.volume_backend.lower() if self.volume_backend else ""

        if backend == "veracrypt":
            return VeraCryptPlatform(
                self.volume_path,
                self.image_path,
                self.show_in_finder,
                self.veracrypt_path,
            )

        if system == "Darwin":
            if backend in ("", "hdiutil"):
                return MacOSPlatform(self.volume_path, self.image_path, self.show_in_finder)
            raise RuntimeError(
                f"Unknown VOLUME_BACKEND '{self.volume_backend}' on macOS. "
                "Use 'hdiutil' or 'veracrypt'."
            )

        if system == "Linux":
            raise RuntimeError(
                "On Linux, set VOLUME_BACKEND=veracrypt in ~/.ppassrc "
                "and install VeraCrypt (https://veracrypt.fr)."
            )

        if system == "Windows":
            return WindowsPlatform(self.volume_path, self.image_path, self.show_in_finder)

        raise RuntimeError(f"Unsupported platform: {system}")

    def is_mounted(self) -> bool:
        """
        Check if the volume is currently mounted.

        Returns:
            True if mounted, False otherwise
        """
        return self.platform.is_mounted()

    def mount(self) -> bool:
        """
        Mount the encrypted volume and start activity tracking.

        Returns:
            True if successful, False otherwise
        """
        if self.is_mounted():
            # Already mounted, just reset activity
            self.activity_tracker.record_activity()
            return True

        # Retry mounting up to max_retries times (mounts can transiently fail,
        # e.g. while a cloud-synced image is still being downloaded).
        success = False
        for _ in range(self.max_retries):
            if self.platform.mount():
                success = True
                break

        if success:
            self.activity_tracker.record_activity()
            if self.auto_unmount:
                self.activity_tracker.start()
        
        return success

    def unmount(self) -> bool:
        """
        Unmount the encrypted volume and stop activity tracking.

        Returns:
            True if successful, False otherwise
        """
        self.activity_tracker.stop()
        return self.platform.unmount()

    def ensure_mounted(self) -> bool:
        """
        Ensure the volume is mounted, mounting if necessary.

        Returns:
            True if mounted, False if mounting failed
        """
        if not self.is_mounted():
            return self.mount()
        
        # Update activity
        self.activity_tracker.record_activity()
        return True

    def _on_inactivity_timeout(self) -> None:
        """Called when inactivity timeout is reached."""
        if self.is_mounted():
            self.unmount()

    def cleanup(self) -> None:
        """Clean up resources."""
        self.activity_tracker.stop()
