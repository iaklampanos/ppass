# ppass - Encrypted Volume Password Manager

A modular Python wrapper around the `pass` password manager that automatically manages encrypted volumes on macOS (with Linux support planned). Perfect for keeping your password store on a shared or cloud drive with automatic mounting and unmounting.

## Features

- **Automatic Volume Management**: Mounts encrypted volumes when needed
- **Auto-unmount**: Automatically unmounts volumes after 5 minutes of inactivity
- **Pass Integration**: Works exactly like `pass` - transparent command proxying
- **Modular Design**: Easy to extend with Linux and other platform support
- **Activity Tracking**: Keeps volumes mounted only when actively in use
- **No External Dependencies**: Uses native system tools (diskutil, hdiutil on macOS)

## Requirements

- macOS 10.12+ (primary target) or Linux
- `pass` password manager installed (`brew install pass`)
- Python 3.9+
- An encrypted volume (APFS or other macOS-supported format)

## Installation

```bash
git clone https://github.com/yourusername/ppass.git
cd ppass
pip install -e .
```

This will install ppass and make the `ppass` command available globally.

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
# Check volume status
ppass --status

# Manually mount
ppass --mount

# Manually unmount
ppass --unmount
```

## Configuration

Configuration is stored in `~/.ppassrc`. After running `ppass --setup`, you can also edit it manually:

```bash
# ppass configuration file (~/.ppassrc)
# See https://github.com/yourusername/ppass for documentation

# Path to the encrypted volume
VOLUME_PATH=/Volumes/PasswordVault

# Password store path inside the encrypted volume
STORE_PATH=.password-store

# Inactivity timeout in seconds (default 300 = 5 minutes)
UNMOUNT_TIMEOUT=300

# Automatically unmount on inactivity (true/false)
AUTO_UNMOUNT=true

# Maximum retries for mount operations
MAX_RETRIES=3
```

Configuration file is readable/writable only by the owner (mode 0600) for security.

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
│   ├── macos.py       # macOS-specific implementation
│   ├── linux.py       # Linux support (planned)
│   └── __init__.py
├── cli.py             # Command-line interface
├── config.py          # Configuration management
└── __init__.py
```

### Adding Platform Support

To add Linux support or other platforms:

1. Create a new class in `ppass/platform/` (e.g., `linux.py`)
2. Inherit from `BasePlatform` in `ppass/platform/base.py`
3. Implement required methods:
   - `is_mounted()`: Check if volume is mounted
   - `mount()`: Mount the volume
   - `unmount()`: Unmount the volume
   - `get_device_identifier()`: Get device info
4. Update platform detection in `ppass/core/volume.py`

See `ppass/platform/linux.py` for an example Linux implementation.

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=ppass --cov-report=html
```

### Code Style

```bash
# Format code
black ppass/ tests/

# Sort imports
isort ppass/ tests/

# Lint
flake8 ppass/ tests/

# Type checking
mypy ppass/
```

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

- macOS support is primary; Linux support is planned
- Requires the `pass` password manager to be installed
- Encrypted volume must be pre-created (ppass doesn't create volumes)
- Requires manual setup for each machine that will use ppass

## Future Enhancements

- [ ] Linux support (placeholder code exists)
- [ ] Interactive setup wizard improvements
- [ ] Shell completion scripts (bash, zsh, fish)
- [ ] Daemon mode for persistent volume monitoring
- [ ] Configuration profiles for different volumes
- [ ] Volume creation/formatting helpers
- [ ] Sync status checking before unmount

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

For issues, questions, or suggestions, please open an issue on GitHub.
