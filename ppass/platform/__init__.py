# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Platform-specific implementations for volume management."""

from ppass.platform.base import BasePlatform
from ppass.platform.veracrypt import VeraCryptPlatform
from ppass.platform.windows import WindowsPlatform

__all__ = ["BasePlatform", "VeraCryptPlatform", "WindowsPlatform"]
