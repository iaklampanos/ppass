# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Windows volume management — stub for future implementation.

On Windows, VeraCrypt mounts containers to a drive letter (e.g. ``V:``)
rather than an arbitrary directory path. The ``VOLUME_PATH`` config key
should hold the drive letter (e.g. ``V:``).

Implementation notes for when this is picked up:
- VeraCrypt binary: ``C:\\Program Files\\VeraCrypt\\VeraCrypt.exe``
  (Git Bash path: ``/c/Program Files/VeraCrypt/VeraCrypt.exe``)
- Mount:   ``VeraCrypt.exe /v <container> /l V /p <passphrase> /a /q``
  Prefer ``/tryemptypass n`` and pipe password via a temp keyfile to avoid
  exposing it in the process list.
- Unmount: ``VeraCrypt.exe /d V /q``
- is_mounted: ``VeraCrypt.exe /l`` lists active slots; parse for volume letter.
- ``pass`` must be available via Git Bash (GNU pass + GnuPG for Windows).
  The PASSWORD_STORE_DIR env var must point to the Unix-style path inside the
  mounted drive (e.g. ``/v/.password-store``).
"""

from typing import Optional

from ppass.platform.base import BasePlatform

_NOT_IMPLEMENTED = (
    "Windows support is not yet implemented. "
    "See ppass/platform/windows.py for implementation notes."
)


class WindowsPlatform(BasePlatform):
    """Stub for future Windows/VeraCrypt support (Git Bash + pass)."""

    def is_mounted(self) -> bool:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def mount(self) -> bool:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def unmount(self) -> bool:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_device_identifier(self) -> Optional[str]:
        raise NotImplementedError(_NOT_IMPLEMENTED)
