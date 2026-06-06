# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the project is in `0.x`, minor versions introduce backward-compatible
functionality and patch versions cover bug fixes, security, and documentation.

## [0.6.0]

### Added
- **VeraCrypt backend** (`VOLUME_BACKEND=veracrypt`): new `VeraCryptPlatform`
  class shared by macOS and Linux. Mounts a VeraCrypt container file (`.vc`)
  via the `veracrypt` CLI. Passphrase is read via `getpass` and piped to
  `veracrypt --stdin`, keeping it out of process-list arguments. The same
  container can be used on a cloud drive across all machines.
- **Windows stubs** (`ppass/platform/windows.py`): `WindowsPlatform` skeleton
  with `NotImplementedError` on all methods and detailed implementation notes
  (VeraCrypt drive-letter mapping, Git Bash / GNU pass integration).
- `VOLUME_BACKEND` config key (`hdiutil` | `veracrypt`); defaults to `hdiutil`
  on macOS and requires explicit `veracrypt` on Linux.
- `VERACRYPT_PATH` config key for non-default VeraCrypt binary locations.
- Setup wizard (`ppass --setup`) now asks for backend, VeraCrypt binary path,
  and image file path; auto-selects `veracrypt` on Linux.
- `pyproject.toml` Python 3.13 / 3.14 classifiers.

### Changed
- `VolumeManager.__init__` accepts `volume_backend` and `veracrypt_path`
  parameters; `_init_platform()` dispatches on backend before OS, so
  `veracrypt` works on both macOS and Linux with the same code path.
- Linux no longer silently falls back to the broken `LinuxPlatform.mount()`;
  it now raises a clear error directing the user to set
  `VOLUME_BACKEND=veracrypt`.
- `.ppassrc.template` restructured with labelled sections for backend,
  paths, behaviour, and backend-specific options.
- `SHOW_IN_FINDER` documented as hdiutil-only; `veracrypt` backend ignores it.

## [0.5.2]

### Added
- MIT `LICENSE` file with copyright notice (Iraklis A. Klampanos).
- SPDX license headers (`SPDX-License-Identifier: MIT` /
  `SPDX-FileCopyrightText`) to all Python source files.
- `__email__` and `__license__` metadata in `ppass/__init__.py`.

### Changed
- `pyproject.toml`: author name and email now reflect the project owner;
  `license` field now references the `LICENSE` file; added Python 3.13 and
  3.14 classifiers.
- CLI banner: colours (bold green name, dimmed box border and reminder line)
  when running in a TTY; falls back to plain text when output is piped.
- `README.md`: licence section now credits the author and links to `LICENSE`.

## [0.5.1]

### Fixed
- `watcher`: retry failed unmounts and keep watching instead of giving up, so a
  volume that is temporarily busy (open file, indexing) is unmounted as soon as
  it becomes free.

### Changed
- `watcher`: replaced the pidfile guard with an exclusive `fcntl.flock` on a
  per-volume lockfile. The lock is held on an open file descriptor for the
  watcher's lifetime, making the single-watcher guarantee immune to PID reuse
  and to races between concurrent invocations, and auto-released by the kernel
  even on `SIGKILL`.

## [0.5.0]

### Added
- Inactivity auto-unmount now works for the one-shot CLI. New `ppass/watcher.py`
  runs as a detached background process, spawned at mount time, that unmounts
  the volume once it has been idle past the timeout (and exits if the volume is
  unmounted by other means).
- `ActivityTracker.reload_last_activity()` so the long-lived watcher observes
  activity recorded by other `ppass` invocations and extends the deadline.

## [0.4.0]

### Added
- `show_in_finder` configuration option (default `true`) controlling whether the
  mounted volume is browsable in Finder. On macOS this toggles the `hdiutil`
  `-nobrowse` flag. Threaded through config, `VolumeManager`, and the platform
  handlers; documented in `.ppassrc.template`.

## [0.3.0]

### Added
- CLI reminder banner ("this is ppass, not pass") printed to stderr on every
  invocation, so it never contaminates stdout when piping a password.

## [0.2.2]

### Documentation
- Expanded the `ppass` package docstring to describe what ppass is, why it is
  useful, and its public API.

## [0.2.1]

### Security
- Relocated the Anthropic API key out of the repository to
  `~/.config/anthropic/key.txt` (`chmod 600`, directory `700`).
- `00_ANTHROPIC_ENV.sh` now reads the key from that external file (overridable
  via `ANTHROPIC_KEY_FILE`), fails clearly if it is missing, and prints only a
  masked confirmation instead of the full secret.

## [0.2.0]

### Added
- `max_retries` is now applied: `VolumeManager.mount()` retries the mount up to
  `max_retries` times. The configured value was previously ignored.

## [0.1.3]

### Fixed
- `ActivityTracker.stop()` no longer joins the monitor thread from within
  itself, which raised `RuntimeError: cannot join current thread` on the
  auto-unmount path.
- macOS `get_device_identifier()`: removed a dead `diskutil list` call and now
  matches the mount point exactly instead of by substring, so `/Volumes/Test`
  no longer matches `/Volumes/TestBackup`.

### Added
- Regression test driving the real inactivity-timeout unmount path, and tests
  for the CLI entry point.

## [0.1.2]

### Security
- Removed the plaintext API key file (`cl_key.txt`) from the repository.
- Added secret patterns (`cl_key.txt`, `00_ANTHROPIC_ENV.sh`, `*_key.txt`,
  `*.key`) to `.gitignore`.

## [0.1.1]

### Fixed
- Deadlock in `ActivityTracker._timeout_monitor`: the timeout callback is now
  invoked outside the lock, instead of while holding the non-reentrant lock that
  the unmount callback re-acquires.
- Config parser no longer coerces numeric `0`/`1` values (e.g. `MAX_RETRIES=1`,
  `UNMOUNT_TIMEOUT=0`) to booleans; boolean parsing is restricted to known
  boolean keys.

## [0.1.0]

### Added
- Initial release: encrypted-volume wrapper for the `pass` password manager,
  with platform-specific mount handling (macOS, Linux), activity tracking, and
  transparent `pass` command proxying.
