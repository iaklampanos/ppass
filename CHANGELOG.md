# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the project is in `0.x`, minor versions introduce backward-compatible
functionality and patch versions cover bug fixes, security, and documentation.

## [0.6.8]

### Security
- **Activity file `open("w")` followed symlinks — local file overwrite possible**
  (`core/activity.py`): `_save_last_activity()` used a plain `open(..., "w")`
  call on a deterministic path in `/tmp`. A local attacker who pre-planted a
  symlink at that path could cause ppass to overwrite any file owned by the
  victim with a float timestamp.

  The call is replaced with `os.open(..., O_WRONLY | O_CREAT | O_TRUNC |
  O_NOFOLLOW, 0o600)` wrapped in `os.fdopen()`. `O_NOFOLLOW` makes the open
  fail with `ELOOP` if the path is a symlink, preventing the attack. The mode
  is now set atomically at creation, so the separate `os.chmod()` call is
  removed.

### Tests
- Added `test_save_last_activity_rejects_symlink` (`test_activity.py`): plants
  a symlink at the tracker path and asserts that `_save_last_activity()` does
  not modify the symlink target.
- Total: 92 tests, all passing; coverage 84%.

## [0.6.7]

### Fixed
- **`~/...` paths in config broken silently** (`platform/base.py`, `core/volume.py`,
  `config.py`): `volume_path` was never passed through `os.path.expanduser()`, so
  `VOLUME_PATH=~/mnt/vc` in `~/.ppassrc` left the literal string `~/mnt/vc`
  everywhere.  This caused `os.makedirs` to create a directory named `~` in the
  working directory, VeraCrypt to fail or mount at the wrong location, and
  `is_mounted()` to always return False (the literal path never appeared in
  `veracrypt --list` output).  `image_path` was expanded in some platform
  subclasses but not `volume_path`, and neither was expanded at the config
  boundary.

  Path expansion is now applied at three layers:
  1. **`load_config()`** — expands `VOLUME_PATH`, `IMAGE_PATH`, and `VERACRYPT_PATH`
     as soon as the config file is read, so all downstream consumers (CLI, watcher)
     receive real paths.
  2. **`VolumeManager.__init__()`** — safety belt for programmatic callers that
     bypass `load_config`.
  3. **`BasePlatform.__init__()`** — deepest defence; covers direct platform
     instantiation in tests or future callers.

  Redundant per-subclass `expanduser` calls in `MacOSPlatform`, `VeraCryptPlatform`,
  and `LinuxPlatform` have been removed.  `VeraCryptPlatform` now also expands
  `veracrypt_path` so `~/bin/veracrypt`-style binary paths work.

### Tests
- Added `test_load_config_expands_tilde_in_paths` (`test_config.py`).
- Added `test_tilde_volume_path_is_expanded` and `test_tilde_image_path_is_expanded`
  (`test_volume.py`).
- Total: 91 tests, all passing; coverage 84%.

### Documentation
- `README.md`: noted `~/...` support in the configuration section; updated the
  architecture diagram to include `veracrypt.py`, `windows.py`, and `watcher.py`;
  removed outdated "Linux support planned" language; simplified "Adding Platform
  Support" section.

## [0.6.6]

### Fixed
- **`VeraCryptPlatform.mount()` leaves orphaned directory on auth failure**
  (`platform/veracrypt.py`): if ppass created the mount-point directory and
  VeraCrypt then rejected the passphrase, the empty directory was left behind.
  The directory is now removed on failure when ppass was the one that created it.
- **`MacOSPlatform.mount()` passes the mount-point path to `hdiutil`** when
  `IMAGE_PATH` is unset (`platform/macos.py`): the code fell through to
  `hdiutil attach <volume_path>`, which errors confusingly. Now prints a clear
  message and returns `False` when no image path is configured.
- **`MacOSPlatform.mount()` silenced `diskutil mount` errors** (`platform/macos.py`):
  `stderr=subprocess.DEVNULL` removed from the APFS device-mount branch so
  authentication failures are visible to the user.
- **`LinuxPlatform.mount()` was a silent unencrypted bind-mount** (`platform/linux.py`):
  the method called `["mount", volume_path]` with no encryption — completely wrong
  for a VeraCrypt volume. Replaced with `NotImplementedError` so accidental use
  fails loudly instead of silently mounting the wrong thing.
- **`VERACRYPT_PATH` dropped from config on backend switch** (`config.py`):
  `save_config()` only wrote `VERACRYPT_PATH` when `volume_backend == "veracrypt"`.
  Switching back to `hdiutil` and then to `veracrypt` silently lost a custom binary
  path. `VERACRYPT_PATH` is now always written.
- **Watcher crash leaves no diagnostic** (`watcher.py`): the detached watcher
  subprocess discarded stderr to `/dev/null`, so any crash (e.g. the FIPS bug
  fixed in 0.6.5) produced no log. Stderr is now redirected to
  `/tmp/.ppass_<hash>_watcher.log`, surviving between restarts and readable with
  `cat`.
- **Watcher lock file accumulates in `/tmp`** (`watcher.py`): the per-volume
  `.ppass_<hash>_watcher.lock` file was never deleted. The lock file is now
  unlinked in the `finally` block before releasing the lock, so it disappears on
  clean exit.
- **Unknown `VOLUME_BACKEND` reached deep into `VolumeManager`** (`cli.py`):
  a typo in `~/.ppassrc` raised an unformatted `RuntimeError` inside
  `VolumeManager.__init__`. The CLI now validates the backend before constructing
  `VolumeManager` and prints a clear "use 'hdiutil' or 'veracrypt'" message.
- **Only `RuntimeError` caught from `VolumeManager` init** (`cli.py`):
  broadened to `except Exception` so `PermissionError`, `ImportError`, and other
  unexpected failures also produce a clean error message rather than a traceback.
- **`--setup` accepts relative image/volume paths without warning** (`cli.py`):
  a relative path resolves against whatever the working directory is at mount time,
  not the user's home. Setup now prints a warning when a non-absolute path is
  entered.
- **`pass generate` not in interactive-command list** (`core/pass_wrapper.py`):
  added `generate` to the set of commands that pass through to a live terminal,
  matching the behaviour of `insert`, `edit`, and `init`.

### Tests
- `TestMacOSPlatform`: fixed `test_mount_success` (now mocks the device so it
  exercises the `diskutil` branch); added `test_mount_errors_without_image_path`.
- `TestLinuxPlatform`: added `test_mount_raises_not_implemented`.
- `TestVeraCryptPlatform`: added `test_mount_removes_created_dir_on_failure`.
- `TestCli`: added `test_unknown_volume_backend_errors`.
- Total: 88 tests, all passing; coverage 83% → 84%.

## [0.6.5]

### Fixed
- **Watcher crashes on FIPS-mode systems** (`watcher.py`): `_volume_key()` called
  `hashlib.md5()` without `usedforsecurity=False`, causing an immediate `ValueError`
  on hardened Linux systems where OpenSSL rejects MD5 by default.  The same fix was
  applied to `core/volume.py` in 0.6.3 but missed here, making auto-unmount silently
  broken on FIPS systems (the watcher process crashed at startup with its stderr
  directed to `/dev/null`).

## [0.6.4]

### Fixed
- **`VeraCryptPlatform.get_device_identifier()` false positive on path prefix**
  (`platform/veracrypt.py`): same substring-match bug fixed in `is_mounted()` in
  0.6.3 was present in `get_device_identifier()` — `/mnt/vc` would incorrectly
  match a line containing `/mnt/vc2`. Now uses token-based matching.  (This
  method is currently dead code, but the inconsistency would silently misbehave
  if it were ever called.)
- **`VeraCryptPlatform.mount()` swallowed VeraCrypt error messages**
  (`platform/veracrypt.py`): `capture_output=True` hid VeraCrypt's stderr (e.g.
  "wrong password") during failed mount attempts, leaving users with no feedback.
  Stderr is now printed to stdout on failure.
- **Activity file world-readable** (`core/activity.py`): the per-volume
  inactivity-timestamp file in `/tmp` was written with default umask permissions
  (0o644), allowing any local user to manipulate the auto-unmount deadline.
  `os.chmod(..., 0o600)` is now applied immediately after writing.
- **`_handle_setup` traceback on Ctrl+C** (`cli.py`): pressing Ctrl+C during
  the interactive setup wizard raised an unhandled `KeyboardInterrupt` and
  printed a traceback. Now caught at the top of `_handle_setup`; exits cleanly
  with "Setup cancelled." and return code 1.

### Tests
- Added `test_get_device_identifier_no_false_positive_on_path_prefix` for the
  token-match fix in `get_device_identifier()`.
- Added `test_mount_prints_stderr_on_failure` verifying VeraCrypt error messages
  reach the user.
- Added `test_activity_file_has_restricted_permissions` confirming 0o600 mode.
- Added `test_setup_keyboard_interrupt_exits_cleanly` for the Ctrl+C fix.
- Total: 84 tests, all passing; coverage 83%.

## [0.6.3]

### Fixed
- **`VeraCryptPlatform.is_mounted()` false positive on path prefix** (`platform/veracrypt.py`):
  `volume_path in result.stdout` was a substring match, so `/mnt/vc` would
  incorrectly match a line containing `/mnt/vc2`.  Now checks whether
  `volume_path` appears as a whole whitespace-delimited token on any output
  line.
- **`ActivityTracker.start()` TOCTOU race** (`core/activity.py`):
  The `_running` guard was checked outside the lock; two concurrent callers
  could both pass it and each start a monitor thread.  Guard moved inside
  `with self._lock`.
- **`hashlib.md5` raises on FIPS-mode systems** (`core/volume.py`):
  Added `usedforsecurity=False` so ppass initialises correctly on hardened
  Linux environments where OpenSSL rejects MD5 by default.
- **`_handle_setup` crashes on non-numeric timeout input** (`cli.py`):
  The bare `int()` conversion now has a `try/except ValueError` that prints a
  clear message and retains the previous value instead of raising an
  unhandled exception.
- **`hdiutil attach` error messages silenced** (`platform/macos.py`):
  Removed `stderr=subprocess.DEVNULL` from the `hdiutil attach` call so
  authentication failures and other errors are visible to the user.

### Tests
- Added `test_is_mounted_no_false_positive_on_path_prefix` for the
  substring-match fix.
- Added `TestSetup.test_invalid_timeout_input_keeps_default` and
  `test_valid_timeout_input_is_applied` for the setup timeout guard.
- Total: 80 tests, all passing; coverage 79% → 83%.

## [0.6.2]

### Fixed
- **Watcher not forwarding volume backend to child process** (`watcher.py`):
  `spawn_watcher()` was building the child command without `--backend` or
  `--veracrypt-path`, so the detached watcher process created `VolumeManager`
  with a blank backend.  On Linux this caused an immediate `RuntimeError`
  (Linux requires `VOLUME_BACKEND=veracrypt`), making auto-unmount silently
  fail for all VeraCrypt users.  On macOS with VeraCrypt the watcher picked
  up `MacOSPlatform` instead of `VeraCryptPlatform`, so it could neither
  detect nor dismount the volume.
  Fixed by adding `--backend` / `--veracrypt-path` CLI args to the watcher
  and forwarding `config.volume_backend` / `config.veracrypt_path` from
  `_start_unmount_watcher()` in the CLI.

### Tests
- Added `TestSpawnWatcherArgs` (3 tests) verifying that `spawn_watcher()`
  embeds `--backend` and `--veracrypt-path` in the child command, and that
  `watcher.run()` constructs `VolumeManager` with the correct backend kwargs.
  Total: 77 tests, all passing.

### Tooling
- Added `scripts/test_veracrypt_linux.sh`: self-contained Docker script that
  installs VeraCrypt on Debian 12 (amd64/arm64 auto-detected), creates a
  20 MB AES container, runs a raw mount/write/unmount/remount/verify cycle,
  then repeats the same cycle through `ppass.core.volume.VolumeManager`.
  Includes a `dmsetup mknodes` workaround for Docker Desktop on macOS, which
  does not run `udevd`.
- Added `*.deb` to `.gitignore`.

## [0.6.1]

### Tests
- Added `tests/test_integration.py` with four lifecycle integration tests
  (`TestVeraCryptLifecycle`): mount-state tracking, secret persistence across
  unmount/remount, multiple categories, and `PASSWORD_STORE_DIR` wiring.
  All pass on macOS (Python 3.14) and Linux (Python 3.12) without requiring
  any external tools — only the veracrypt binary is mocked.
- Fixed `test_platform_selection_linux` to assert `RuntimeError` (Linux now
  requires `VOLUME_BACKEND=veracrypt`).
- Fixed `test_platform_unsupported` to use a truly unsupported OS (`SunOS`)
  rather than Windows, which now returns a `WindowsPlatform` stub.
- Added `TestVeraCryptPlatform` (14 tests, 94% coverage) and
  `TestWindowsPlatform` (4 tests, 100% coverage).
- Added backend-selection tests for Linux+veracrypt, macOS+veracrypt,
  macOS+unknown backend, and Windows stub.
- Added CLI tests: mount success, unmount failure, status not mounted,
  verbose flag.
- Added config round-trip tests for `volume_backend` and `veracrypt_path`.
- Overall unit-test coverage: 68% → 76%; 74 tests, all passing.

### Documentation
- README: fixed GitHub URLs, updated installation to `pipx`, added VeraCrypt
  requirements and backend section, updated configuration and development
  sections, revised limitations and future enhancements.

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
