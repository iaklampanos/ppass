# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Per-user runtime state directory and subprocess-environment hardening.

ppass keeps small state files outside the encrypted volume: the activity
timestamp, the watcher lockfile, and the watcher log. On Linux the system temp
directory is usually the world-writable, sticky ``/tmp``, where predictable
filenames invite symlink and pre-creation attacks by other local users. To
contain that, all such state lives in a single per-user directory created with
mode ``0700`` and verified to be owned by the current user (see
:func:`runtime_dir`).

This module also provides :func:`secure_env`, used when spawning external
binaries (``pass``, ``veracrypt``, ``diskutil`` …) so that ``PATH`` cannot be
hijacked via empty/relative or world-writable entries.
"""

import os
import stat
import tempfile

# Allowance (seconds) for a future-dated activity timestamp. Same-machine
# timestamps share one clock, so a value meaningfully ahead of "now" is either
# corruption or tampering; a small margin absorbs benign clock jitter.
MAX_CLOCK_SKEW = 60


def _user_tag() -> str:
    """A stable, per-user component for the runtime directory name."""
    getuid = getattr(os, "getuid", None)
    if getuid is not None:
        return str(getuid())
    return os.environ.get("USERNAME", "user")


def runtime_dir() -> str:
    """Return ppass's private state directory, creating it if necessary.

    Prefers ``$XDG_RUNTIME_DIR`` (already a per-user ``0700`` location on modern
    Linux); otherwise uses a ``ppass-<uid>`` subdirectory of the system temp
    dir. The directory is created with mode ``0700``. If it already exists it
    must be a real directory (not a symlink) owned by the current user,
    otherwise a :class:`RuntimeError` is raised rather than risk using a path an
    attacker could have pre-created.
    """
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base and os.path.isdir(base):
        path = os.path.join(base, "ppass")
    else:
        path = os.path.join(tempfile.gettempdir(), f"ppass-{_user_tag()}")

    _ensure_private_dir(path)
    return path


def _ensure_private_dir(path: str) -> None:
    """Create *path* as a 0700 directory, or verify an existing one is safe."""
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    # Any other OSError propagates: we must not silently fall back to an
    # unprotected location.

    info = os.lstat(path)  # lstat: do not follow a symlink planted at the path
    if not stat.S_ISDIR(info.st_mode):
        raise RuntimeError(f"ppass state path is not a directory: {path}")

    getuid = getattr(os, "getuid", None)
    if getuid is not None and info.st_uid != getuid():
        raise RuntimeError(
            f"ppass state directory {path} is not owned by the current user; "
            "refusing to use it."
        )

    # Tighten permissions if a pre-existing directory is group/other-accessible.
    if info.st_mode & 0o077 and hasattr(os, "chmod"):
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass


def secure_path() -> str:
    """Return ``$PATH`` with insecure entries removed (order preserved).

    Drops empty and relative entries (``""`` / ``.`` resolve against the current
    working directory — a classic binary-hijacking vector) and any
    world-writable directory lacking the sticky bit (anyone could drop a
    malicious binary there).
    """
    raw = os.environ.get("PATH", os.defpath)
    safe = []
    for entry in raw.split(os.pathsep):
        if not entry or not os.path.isabs(entry):
            continue
        try:
            info = os.stat(entry)
        except OSError:
            continue
        if info.st_mode & stat.S_IWOTH and not info.st_mode & stat.S_ISVTX:
            continue
        safe.append(entry)
    return os.pathsep.join(safe)


def secure_env() -> dict:
    """A copy of the current environment with a sanitized ``PATH``.

    Passed as ``env=`` to :func:`subprocess.run`/``Popen``. Python resolves a
    bare executable name against this ``PATH`` (via :func:`os.get_exec_path`), so
    overriding it here hardens binary resolution without having to hardcode
    absolute paths for every system tool.
    """
    env = os.environ.copy()
    env["PATH"] = secure_path()
    return env
