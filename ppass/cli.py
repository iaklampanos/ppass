# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Command-line interface for ppass."""

import sys
import argparse
import os
from typing import Optional

from ppass import __version__
from ppass.core.volume import VolumeManager
from ppass.core.pass_wrapper import PassWrapper
from ppass.config import load_config, save_config
from ppass.watcher import spawn_watcher


def _start_unmount_watcher(config) -> None:
    """Ensure a detached inactivity-unmount watcher is running for the volume.

    ppass exits after each command, so the actual auto-unmount is performed by
    a separate background process (see ppass.watcher). This is a no-op when
    auto-unmount is disabled or a watcher is already running.
    """
    if config.auto_unmount:
        spawn_watcher(
            config.volume_path,
            config.image_path,
            config.unmount_timeout,
            config.volume_backend,
            config.veracrypt_path,
        )


def _print_banner() -> None:
    """Print a reminder banner so it's clear this is ppass, not pass.

    Written to stderr so it never contaminates stdout (e.g. when piping a
    password with ``ppass show entry | pbcopy``).
    """
    use_color = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    B = "\033[1m"  if use_color else ""   # bold
    G = "\033[32m" if use_color else ""   # green
    D = "\033[2m"  if use_color else ""   # dim
    R = "\033[0m"  if use_color else ""   # reset

    ver = f"v{__version__}"
    title_vis = f" ppass {ver} "
    title_col = f" {B}{G}ppass{R} {ver} "

    body_vis = [
        "encrypted-volume wrapper for pass",
        "this is ppass, not pass",
    ]
    body_col = [body_vis[0], f"{D}{body_vis[1]}{R}"]

    inner = max(len(title_vis) + 1, max(2 + len(t) + 2 for t in body_vis))
    top_fill = inner - 1 - len(title_vis)

    e = sys.stderr
    print(f"{D}╭─{R}{title_col}{D}{'─' * top_fill}╮{R}", file=e)
    for vis, col in zip(body_vis, body_col):
        pad = inner - 2 - len(vis)
        print(f"{D}│{R}  {col}{' ' * pad}{D}│{R}", file=e)
    print(f"{D}╰{'─' * inner}╯{R}", file=e)


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for ppass CLI.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        prog="ppass",
        description="Encrypted volume wrapper for pass password manager",
        add_help=False  # We'll handle help manually to proxy to pass
    )
    
    # ppass-specific arguments
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Setup ppass configuration"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show volume mount status"
    )
    parser.add_argument(
        "--mount",
        action="store_true",
        help="Mount the encrypted volume"
    )
    parser.add_argument(
        "--unmount",
        action="store_true",
        help="Unmount the encrypted volume"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    # All remaining arguments are passed to pass
    parser.add_argument(
        "pass_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to pass"
    )
    
    args = parser.parse_args(argv)

    # Remind the user this is ppass (not pass) on every invocation.
    _print_banner()

    # Check if first positional arg is a ppass command
    if args.pass_args and args.pass_args[0] in ("status", "mount", "unmount", "setup"):
        ppass_cmd = args.pass_args[0]
        args.pass_args = args.pass_args[1:]  # Remove the command from pass_args
        
        if ppass_cmd == "status":
            args.status = True
        elif ppass_cmd == "mount":
            args.mount = True
        elif ppass_cmd == "unmount":
            args.unmount = True
        elif ppass_cmd == "setup":
            args.setup = True
    
    # Load configuration
    config = load_config(args.config)
    
    if args.verbose:
        config.verbose = True
    
    # Handle setup
    if args.setup:
        return _handle_setup(config, args.config)
    
    # Validate configuration
    if not config.volume_path:
        print("Error: volume_path not configured. Run 'ppass --setup' first.", file=sys.stderr)
        return 1
    
    # Initialize volume manager
    try:
        vm = VolumeManager(
            volume_path=config.volume_path,
            image_path=config.image_path,
            inactivity_timeout=config.unmount_timeout,
            auto_unmount=config.auto_unmount,
            max_retries=config.max_retries,
            show_in_finder=config.show_in_finder,
            volume_backend=config.volume_backend,
            veracrypt_path=config.veracrypt_path,
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    # Handle volume-specific commands
    if args.status:
        mounted = vm.is_mounted()
        status = "mounted" if mounted else "not mounted"
        print(f"Volume {config.volume_path}: {status}")
        
        # Show remaining time if mounted and auto-unmount is enabled
        if mounted and config.auto_unmount:
            remaining = vm.activity_tracker.get_remaining_time()
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            print(f"Auto-unmount in: {mins}m {secs}s")
        
        return 0
    
    if args.mount:
        success = vm.mount()
        if success:
            _start_unmount_watcher(config)
            print(f"Volume mounted: {config.volume_path}")
            return 0
        else:
            print(f"Error: Failed to mount volume", file=sys.stderr)
            return 1
    
    if args.unmount:
        success = vm.unmount()
        if success:
            print(f"Volume unmounted: {config.volume_path}")
            return 0
        else:
            print(f"Error: Failed to unmount volume", file=sys.stderr)
            return 1
    
    # If no ppass-specific args, proxy to pass
    pass_args = args.pass_args if args.pass_args else ["--help"]
    
    # Ensure volume is mounted before running pass
    if not vm.ensure_mounted():
        print("Error: Failed to mount volume", file=sys.stderr)
        return 1

    # Make sure a background watcher will unmount the volume once it goes idle.
    _start_unmount_watcher(config)

    try:
        # Initialize pass wrapper
        store_path = os.path.join(config.volume_path, config.store_path)
        pw = PassWrapper(store_path)
        
        if config.verbose:
            print(f"[ppass] Using store: {store_path}", file=sys.stderr)
            print(f"[ppass] Command: pass {' '.join(pass_args)}", file=sys.stderr)
        
        # Execute pass command
        rc, stdout, stderr = pw.execute(pass_args)
        
        if stdout:
            print(stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)
        
        # Update activity
        vm.activity_tracker.record_activity()
        
        return rc
    
    finally:
        vm.cleanup()


def _handle_setup(config, config_path: Optional[str]) -> int:
    """Handle the --setup interactive configuration."""
    import platform as _platform

    print("ppass Configuration Setup")
    print("=" * 40)

    system = _platform.system()

    # --- Volume backend ---
    if system == "Linux":
        # Only veracrypt is supported on Linux
        backend = "veracrypt"
        print("Volume backend: veracrypt (only option on Linux)")
    else:
        current_backend = config.volume_backend or "hdiutil"
        backend_input = input(
            f"Volume backend — 'hdiutil' (macOS sparsebundle/dmg) or "
            f"'veracrypt' (cross-platform) [{current_backend}]: "
        ).strip().lower() or current_backend
        if backend_input not in ("hdiutil", "veracrypt"):
            print(f"Unknown backend '{backend_input}', defaulting to 'hdiutil'.")
            backend_input = "hdiutil"
        backend = backend_input
    config.volume_backend = backend

    # --- VeraCrypt binary path (only when backend is veracrypt) ---
    if backend == "veracrypt":
        veracrypt_path = input(
            f"Path to veracrypt binary [{config.veracrypt_path or 'veracrypt'}]: "
        ).strip() or config.veracrypt_path or "veracrypt"
        config.veracrypt_path = veracrypt_path

    # --- Image and volume paths ---
    image_path = input(
        f"Path to encrypted image file [{config.image_path}]: "
    ).strip() or config.image_path

    volume_path = input(
        f"Mount point for the volume [{config.volume_path}]: "
    ).strip() or config.volume_path

    store_path = input(
        f"Password store path inside volume [{config.store_path}]: "
    ).strip() or config.store_path

    timeout_input = input(
        f"Unmount timeout in seconds [{config.unmount_timeout}]: "
    ).strip()
    unmount_timeout = int(timeout_input) if timeout_input else config.unmount_timeout

    # Update config
    config.image_path = image_path
    config.volume_path = volume_path
    config.store_path = store_path
    config.unmount_timeout = unmount_timeout

    # Save configuration
    try:
        save_config(config, config_path)
        print(f"\nConfiguration saved to ~/.ppassrc")
        print(f"Backend:        {backend}")
        print(f"Image path:     {image_path}")
        print(f"Volume path:    {volume_path}")
        print(f"Store path:     {store_path}")
        print(f"Unmount timeout:{unmount_timeout}s")
        return 0
    except Exception as e:
        print(f"Error saving configuration: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
