# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Configuration management for ppass."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Configuration for ppass."""

    # Volume paths
    volume_path: str
    image_path: str = ""
    store_path: str = ".password-store"

    # Volume backend: "hdiutil" (macOS sparsebundle/dmg) or "veracrypt" (cross-platform)
    # Leave empty to use the OS default (hdiutil on macOS).
    volume_backend: str = ""

    # Path to the veracrypt binary; override when not on PATH.
    veracrypt_path: str = "veracrypt"

    # Timeouts and behavior
    unmount_timeout: int = 300  # 5 minutes in seconds
    max_retries: int = 3
    auto_unmount: bool = True
    show_in_finder: bool = True  # Show the mounted volume in Finder (hdiutil only)

    # Display options
    verbose: bool = False


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from ~/.ppassrc file.

    Args:
        config_path: Path to config file. If None, uses ~/.ppassrc

    Returns:
        Config instance
    """
    if config_path is None:
        config_path = os.path.expanduser("~/.ppassrc")
    
    config_dict = {}
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue
                    # Parse key=value pairs
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip().lower()
                        value = value.strip()
                        
                        # Parse booleans (only for known boolean keys, so that
                        # numeric values like "0"/"1" are not coerced to bools)
                        if key in ("auto_unmount", "verbose", "show_in_finder"):
                            config_dict[key] = value.lower() in ("true", "yes", "1")
                        # Parse integers
                        elif key in ("unmount_timeout", "max_retries"):
                            try:
                                config_dict[key] = int(value)
                            except ValueError:
                                pass
                        # Plain strings (including volume_backend, veracrypt_path)
                        else:
                            config_dict[key] = value
        except IOError as e:
            print(f"Warning: Could not load config file {config_path}: {e}")
    
    return Config(
        volume_path=config_dict.get("volume_path", ""),
        image_path=config_dict.get("image_path", ""),
        store_path=config_dict.get("store_path", ".password-store"),
        volume_backend=config_dict.get("volume_backend", ""),
        veracrypt_path=config_dict.get("veracrypt_path", "veracrypt"),
        unmount_timeout=config_dict.get("unmount_timeout", 300),
        max_retries=config_dict.get("max_retries", 3),
        auto_unmount=config_dict.get("auto_unmount", True),
        show_in_finder=config_dict.get("show_in_finder", True),
        verbose=config_dict.get("verbose", False),
    )


def save_config(config: Config, config_path: Optional[str] = None) -> None:
    """
    Save configuration to ~/.ppassrc file.

    Args:
        config: Config instance to save
        config_path: Path to config file. If None, uses ~/.ppassrc
    """
    if config_path is None:
        config_path = os.path.expanduser("~/.ppassrc")
    
    # Create directory if needed (for custom paths)
    os.makedirs(os.path.dirname(config_path) or ".", exist_ok=True)
    
    lines = [
        "# ppass configuration file",
        "# See https://github.com/iaklampanos/ppass for documentation",
        "",
        "# Volume backend: 'hdiutil' (macOS sparsebundle/dmg) or 'veracrypt' (cross-platform)",
        f"VOLUME_BACKEND={config.volume_backend}",
        "",
        "# Path to the encrypted volume image file",
        f"IMAGE_PATH={config.image_path}",
        "",
        "# Mount point for the encrypted volume",
        f"VOLUME_PATH={config.volume_path}",
        "",
        "# Password store path inside the encrypted volume",
        f"STORE_PATH={config.store_path}",
        "",
        "# Inactivity timeout in seconds (default 300 = 5 minutes)",
        f"UNMOUNT_TIMEOUT={config.unmount_timeout}",
        "",
        "# Automatically unmount on inactivity (true/false)",
        f"AUTO_UNMOUNT={'true' if config.auto_unmount else 'false'}",
        "",
        "# Show the mounted volume in Finder — hdiutil backend only (true/false)",
        f"SHOW_IN_FINDER={'true' if config.show_in_finder else 'false'}",
        "",
        "# Maximum retries for mount operations",
        f"MAX_RETRIES={config.max_retries}",
    ]
    if config.volume_backend == "veracrypt":
        lines += [
            "",
            "# Path to the veracrypt binary (override if not on PATH)",
            f"VERACRYPT_PATH={config.veracrypt_path}",
        ]
    
    with open(config_path, "w") as f:
        f.write("\n".join(lines))
    
    # Set readable only by owner for security
    os.chmod(config_path, 0o600)
