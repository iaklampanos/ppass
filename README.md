# ppass - Encrypted Volume Password Manager

A modular Python wrapper around the `pass` password manager that automatically manages encrypted volumes on macOS and Linux. Perfect for keeping your password store on a shared or cloud drive with automatic mounting and unmounting.

## Features

- **Two volume backends**: native macOS sparsebundle/dmg via `hdiutil`, or cross-platform VeraCrypt containers
- **Same container on all machines**: VeraCrypt volumes on a cloud drive work identically on macOS and Linux
- **Automatic Volume Management**: Mounts encrypted volumes on demand
- **Auto-unmount**: Automatically unmounts after a configurable inactivity timeout (default 5 minutes)
- **Pass Integration**: Transparent `pass` command proxying — use it exactly like `pass`
- **Activity Tracking**: Keeps volumes mounted only while actively in use
- **No extra runtime dependencies**: native backend uses macOS system tools; VeraCrypt backend only requires the `veracrypt` CLI

## Requirements

- Python 3.9+
- `pass` password manager (`brew install pass` on macOS)
- **hdiutil backend** (macOS only): no extra tools — uses system `hdiutil`/`diskutil`
- **VeraCrypt backend** (macOS + Linux): `veracrypt` CLI installed
  - macOS: `brew install --cask veracrypt`
  - Linux: package manager or [veracrypt.fr](https://veracrypt.fr/en/Downloads.html)

## Installation

```bash
git clone https://github.com/iaklampanos/ppass.git
cd ppass
pipx install -e .
```

`pipx` installs ppass in an isolated environment and puts the `ppass` command on your PATH. If you don't have `pipx`: `brew install pipx && pipx ensurepath`.

## Quick Start

### 1. Initial Setup

```bash
ppass --setup
```

This will prompt you for:
- Path to your encrypted volume
- Password store path inside the volume
- Unmount timeout (default: 5 minutes)

### 2. Use Like `pass`

```bash
# Show passwords
ppass show mail/gmail

# Generate new password
ppass generate mail/gmail 32

# Insert new password
ppass insert mail/gmail

# List all passwords
ppass

# Any other pass command
ppass <command> [options]
```

### 3. Manual Volume Control

```bash
# List all ppass-specific commands
ppass help

# Show current configuration
ppass config

# Check volume status
ppass --status

# Manually mount
ppass --mount

# Manually unmount
ppass --unmount

# Eject (unmount) the volume immediately
ppass eject
```

## Configuration

Run `ppass --setup` for an interactive wizard, or edit `~/.ppassrc` directly (mode 0600 — owner-only).

```bash
# Volume backend: 'hdiutil' (macOS sparsebundle/dmg) or 'veracrypt' (cross-platform)
VOLUME_BACKEND=hdiutil

# Path to the encrypted volume image file  (~/... paths are supported)
IMAGE_PATH=~/cloud/ppass.sparsebundle   # or ~/cloud/ppass.vc for VeraCrypt

# Mount point for the encrypted volume  (~/... paths are supported)
VOLUME_PATH=/Volumes/ppass              # macOS example
# VOLUME_PATH=~/mnt/ppass              # Linux example

# Password store path inside the encrypted volume
STORE_PATH=.password-store

# Inactivity timeout in seconds (default 300 = 5 minutes)
UNMOUNT_TIMEOUT=300

# Automatically unmount on inactivity (true/false)
AUTO_UNMOUNT=true

# Maximum retries for mount operations
MAX_RETRIES=3

# --- hdiutil-specific ---
# Show the mounted volume in Finder (true/false)
SHOW_IN_FINDER=true

# --- VeraCrypt-specific ---
# Path to the veracrypt binary (override if not on PATH)
# VERACRYPT_PATH=veracrypt
```

See `.ppassrc.template` in the repository for a fully commented example.

## VeraCrypt Backend

VeraCrypt containers (`.vc` files) work identically on macOS and Linux, making them ideal for a password store on a cloud drive shared across machines.

```bash
# 1. Create a VeraCrypt container (using the VeraCrypt GUI or CLI)
#    and place it on your cloud drive, e.g. ~/Dropbox/ppass.vc

# 2. Configure ppass
ppass --setup
# → choose 'veracrypt' as backend
# → set IMAGE_PATH to ~/Dropbox/ppass.vc
# → set VOLUME_PATH to /Volumes/ppass (macOS) or ~/mnt/ppass (Linux)

# 3. Use normally — ppass prompts for your VeraCrypt passphrase on first mount
ppass show email/gmail
```

The passphrase is read via a hidden prompt and piped to `veracrypt --stdin`, so it never appears in the process list.

## How It Works

1. **Command Received**: User runs `ppass show mail/gmail`
2. **Volume Check**: ppass checks if the encrypted volume is mounted
3. **Mount if Needed**: If not mounted, automatically mounts it
4. **Activity Reset**: Resets the inactivity timer
5. **Execute Pass**: Runs the `pass` command with the provided arguments
6. **Return Result**: Returns output to the user
7. **Auto-unmount**: After the configured timeout without activity, unmounts the volume

## Architecture

The project uses a modular architecture to support multiple platforms:

```
ppass/
├── core/
│   ├── volume.py       # Volume lifecycle (mount/unmount)
│   ├── pass_wrapper.py # Pass command execution
│   ├── activity.py     # Activity tracking and timeouts
│   └── __init__.py
├── platform/
│   ├── base.py        # Abstract platform interface
│   ├── macos.py       # macOS hdiutil implementation
│   ├── veracrypt.py   # VeraCrypt implementation (macOS + Linux)
│   ├── linux.py       # Linux placeholder (use VeraCrypt backend)
│   ├── windows.py     # Windows stubs (not yet implemented)
│   └── __init__.py
├── cli.py             # Command-line interface
├── config.py          # Configuration management
├── watcher.py         # Detached auto-unmount watcher process
└── __init__.py
```

### Adding Platform Support

To add support for a new platform or backend:

1. Create a new class in `ppass/platform/` inheriting from `BasePlatform`
2. Implement the four abstract methods: `is_mounted()`, `mount()`, `unmount()`, `get_device_identifier()`
3. Update `VolumeManager._init_platform()` in `ppass/core/volume.py` to dispatch to the new class

## Development

Dev tools (pytest, black, mypy, flake8, isort) are installed into the pipx environment alongside ppass:

```bash
# Run tests
~/.local/pipx/venvs/ppass/bin/pytest

# Format code
~/.local/pipx/venvs/ppass/bin/black ppass/ tests/

# Sort imports
~/.local/pipx/venvs/ppass/bin/isort ppass/ tests/

# Lint
~/.local/pipx/venvs/ppass/bin/flake8 ppass/ tests/

# Type checking
~/.local/pipx/venvs/ppass/bin/mypy ppass/
```

Or activate the pipx venv first: `source ~/.local/pipx/venvs/ppass/bin/activate`, then use the tools directly.

## Troubleshooting

### Volume won't mount

- Ensure the encrypted volume is accessible and not already mounted elsewhere
- Check that the device is connected (for external volumes)
- Verify you have proper permissions with `sudo`
- Check system logs: `log stream --predicate 'process == "ppass"'`

### Pass command not found

```bash
# Install pass
brew install pass

# Verify pass is installed
which pass
pass --version
```

### Timeout not working

- Check that activity tracking is enabled: `ppass --verbose` shows debug info
- Verify the timeout value: `ppass --status` and `grep unmount_timeout ~/.ppass/config.yml`
- Ensure ppass process isn't hanging: check process list with `ps aux | grep ppass`

### Permission denied errors

```bash
# Grant ppass execute permission
chmod +x $(which ppass)

# May need sudo for mount operations
sudo ppass --mount
```

## Example Workflow

```bash
# First time: setup
$ ppass --setup
ppass Configuration Setup
========================================
Encrypted volume path []: /Volumes/PasswordVault
Password store path inside volume [.password-store]: .password-store
Unmount timeout in seconds [300]: 300

Configuration saved!

# Use like normal pass
$ ppass show mail/gmail
# Volume mounts automatically
# Password is displayed
# After 5 minutes of inactivity, volume unmounts automatically

# Check status anytime
$ ppass --status
Volume /Volumes/PasswordVault: mounted
```

## Security Considerations

- **Volume Encryption**: Ensure your volume is encrypted (APFS encryption recommended on macOS)
- **Pass Encryption**: pass uses GPG by default - ensure your GPG setup is secure
- **Inactivity Timeout**: 5 minutes is the default - adjust based on your security needs
- **Shared Drives**: This tool is designed for use with shared/cloud drives - ensure they're synced before unmounting
- **Permissions**: Only your user should have access to the volume mount point

## Limitations

- Encrypted volume must be pre-created (ppass does not create volumes)
- Requires manual setup on each machine
- Windows support is stubbed but not yet implemented
- VeraCrypt volumes must be pre-created (ppass does not create new containers)

## Future Enhancements

- [ ] Windows support (VeraCrypt + Git Bash + pass — stubs in `ppass/platform/windows.py`)
- [ ] Shell completion scripts (bash, zsh, fish)
- [ ] Sync status check before unmount (for cloud-backed volumes)
- [ ] Configuration profiles for multiple volumes
- [ ] Volume creation/formatting helpers

## License

Copyright (c) 2026 [Iraklis A. Klampanos](mailto:iraklis@tuta.com)

This project is licensed under the [MIT License](LICENSE).

## Contributing

Contributions are welcome! Please ensure:

1. Code follows PEP 8 style guidelines
2. New features include tests
3. Platform-specific code is kept in separate modules
4. All tests pass: `pytest`
5. Code is formatted with black and isort

## Support

For issues, questions, or suggestions, open an issue at https://github.com/iaklampanos/ppass.
