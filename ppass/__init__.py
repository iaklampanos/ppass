# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""ppass - Encrypted Volume Password Manager.

ppass is a modular Python wrapper around the ``pass`` password manager that
automatically manages the encrypted volume your password store lives on. It
mounts the volume on demand when you run a command and unmounts it again after
a period of inactivity, so your secrets are only exposed while you are actively
using them.

Why it's useful:

- **Keep your store on shared or cloud drives safely.** The password store can
  sit on an encrypted volume (APFS, ``.dmg``/``.sparsebundle``, etc.) backed by
  a cloud-synced or shared disk, while the decrypted contents are only mounted
  when needed.
- **Automatic mount/unmount.** Volumes are mounted just-in-time and auto-
  unmounted after an inactivity timeout (default 5 minutes), shrinking the
  window in which plaintext secrets are accessible.
- **Transparent ``pass`` proxying.** ppass forwards commands straight through to
  ``pass``, so it behaves exactly like the tool you already know.
- **Cross-platform by design.** Platform-specific mount logic is isolated behind
  a common interface, with macOS support today and Linux support in progress.
- **No external dependencies.** It drives native system tools (``diskutil`` and
  ``hdiutil`` on macOS) rather than pulling in third-party packages.

Public API:

- :class:`~ppass.core.volume.VolumeManager` - volume lifecycle (mount/unmount)
  with activity tracking.
- :class:`~ppass.core.pass_wrapper.PassWrapper` - thin wrapper around the
  ``pass`` CLI.
- :class:`~ppass.core.activity.ActivityTracker` - inactivity timeout management.
"""

__version__ = "0.6.6"
__author__ = "Iraklis A. Klampanos"
__email__ = "iraklis@tuta.com"
__license__ = "MIT"

from ppass.core.volume import VolumeManager
from ppass.core.pass_wrapper import PassWrapper
from ppass.core.activity import ActivityTracker

__all__ = ["VolumeManager", "PassWrapper", "ActivityTracker", "__version__"]
