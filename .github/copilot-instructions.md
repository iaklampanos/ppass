# Copilot Instructions for ppass

This file provides guidance for GitHub Copilot when working on the ppass project.

## Project Overview

ppass is a Python-based encrypted volume wrapper for the `pass` password manager, designed to automatically manage encrypted volumes on macOS with Linux support planned.

## Code Organization

- **`ppass/core/`**: Core functionality (volume management, pass wrapper, activity tracking)
- **`ppass/platform/`**: Platform-specific implementations (macOS, Linux)
- **`ppass/cli.py`**: Command-line interface
- **`ppass/config.py`**: Configuration management
- **`tests/`**: Unit tests

## Key Design Patterns

1. **Abstract Base Class**: `BasePlatform` in `ppass/platform/base.py` defines the interface for platform implementations
2. **Activity Tracking**: `ActivityTracker` uses threading to monitor inactivity and trigger timeouts
3. **Configuration Management**: YAML-based configuration with sensible defaults
4. **Subprocess Wrapping**: Safe subprocess execution with timeouts for system commands

## When Implementing Features

1. Keep platform-specific code in `ppass/platform/`
2. Add tests for new functionality in `tests/`
3. Update configuration handling in `ppass/config.py` for new settings
4. Use type hints for better IDE support
5. Handle subprocess errors gracefully
6. Ensure cross-platform compatibility where possible

## Common Tasks

### Adding a new platform
1. Create `ppass/platform/newplatform.py`
2. Inherit from `BasePlatform`
3. Implement all abstract methods
4. Update `VolumeManager._init_platform()` to detect and use the new platform
5. Add tests in `tests/test_platform.py`

### Adding a new CLI option
1. Add argument to parser in `ppass/cli.py`
2. Implement handler function
3. Update `main()` to call the handler
4. Document in README.md

### Adding a new configuration option
1. Add field to `Config` dataclass in `ppass/config.py`
2. Update `load_config()` and `save_config()`
3. Update setup prompt in `ppass/cli.py`
4. Document in README.md

## Testing Guidelines

- Use `unittest.mock.patch` for subprocess mocking
- Mock platform calls to avoid actual system operations in tests
- Test both success and failure paths
- Aim for >80% code coverage

## Code Style

- PEP 8 compliant
- Use black for formatting: `black ppass/ tests/`
- Use isort for imports: `isort ppass/ tests/`
- Use mypy for type checking: `mypy ppass/`
- Maximum line length: 100 characters

## Dependencies

- **Core**: None (uses only Python stdlib and system commands)
- **Dev**: pytest, pytest-cov, black, isort, flake8, mypy
- **Note**: No external dependencies for core functionality

## Important Notes

1. **Subprocess Safety**: All subprocess calls should use:
   - `capture_output=True` for safety
   - `timeout` parameter to prevent hanging
   - `text=True` for string output
   - Error handling for `TimeoutExpired` and `FileNotFoundError`

2. **Thread Safety**: `ActivityTracker` uses locks - maintain thread safety for any modifications

3. **Cross-Platform**: Be mindful of:
   - Different subprocess behavior on macOS vs Linux
   - Different path formats
   - Different system tools availability

4. **Volume Safety**: Respect user preferences for `auto_unmount` setting - don't force unmounting if disabled

## Debugging

- Run with `--verbose` flag for debug output
- Check configuration: `cat ~/.ppassrc`
- Check mount status: `ppass --status`
- Review logs with: `log stream --predicate 'process == "ppass"'` (macOS)
