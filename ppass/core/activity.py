# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Iraklis A. Klampanos <iraklis@tuta.com>

"""Activity tracking and inactivity timeout management."""

import threading
import time
import os
import tempfile
from typing import Callable, Optional


class ActivityTracker:
    """Tracks activity and manages inactivity timeouts."""

    def __init__(self, inactivity_timeout: int = 300, on_timeout: Optional[Callable] = None, tracker_id: str = "ppass"):
        """
        Initialize activity tracker.

        Args:
            inactivity_timeout: Seconds before timeout (default 300 = 5 minutes)
            on_timeout: Callback function to execute on timeout
            tracker_id: Identifier for persistent activity state file
        """
        self.inactivity_timeout = inactivity_timeout
        self.on_timeout = on_timeout
        self.tracker_id = tracker_id
        self._tracker_file = os.path.join(tempfile.gettempdir(), f".{tracker_id}_activity")
        
        # Try to load last activity time from persistent storage, falling back
        # to "now" when there is no valid persisted value.
        loaded = self._load_last_activity()
        self.last_activity = loaded if loaded is not None else time.time()
        
        self._timeout_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    def _load_last_activity(self) -> Optional[float]:
        """Load last activity time from persistent storage.

        Returns the stored timestamp, or None if there is no readable/valid
        persisted value (so callers can decide on a fallback).
        """
        try:
            if os.path.exists(self._tracker_file):
                with open(self._tracker_file, "r") as f:
                    return float(f.read().strip())
        except (IOError, ValueError):
            pass
        return None

    def reload_last_activity(self) -> None:
        """Refresh last_activity from persistent storage.

        Used by the long-running unmount watcher so it observes activity
        recorded by other (short-lived) ppass invocations. A missing or invalid
        file leaves the in-memory value unchanged.
        """
        with self._lock:
            loaded = self._load_last_activity()
            if loaded is not None:
                self.last_activity = loaded

    def _save_last_activity(self) -> None:
        """Save last activity time to persistent storage."""
        try:
            fd = os.open(
                self._tracker_file,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(fd, "w") as f:
                f.write(str(self.last_activity))
        except OSError:
            pass

    def record_activity(self) -> None:
        """Record an activity event, resetting the inactivity timer."""
        with self._lock:
            self.last_activity = time.time()
            self._save_last_activity()

    def start(self) -> None:
        """Start the inactivity timeout monitor thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._timeout_thread = threading.Thread(
                target=self._timeout_monitor,
                daemon=True,
                name="ActivityTimeoutMonitor"
            )
            self._timeout_thread.start()

    def stop(self) -> None:
        """Stop the inactivity timeout monitor thread."""
        with self._lock:
            self._running = False

        # Don't join when stop() is invoked from the monitor thread itself
        # (e.g. via an on_timeout -> unmount -> stop callback chain): a thread
        # cannot join itself, and the loop already exits once _running is False.
        if self._timeout_thread and self._timeout_thread is not threading.current_thread():
            self._timeout_thread.join(timeout=2)

    def _timeout_monitor(self) -> None:
        """Monitor inactivity and trigger timeout callback if needed."""
        while self._running:
            with self._lock:
                elapsed = time.time() - self.last_activity
                timed_out = elapsed > self.inactivity_timeout and self.on_timeout is not None

            # Invoke the callback OUTSIDE the lock. The callback may call back
            # into this tracker (e.g. stop()), and self._lock is non-reentrant,
            # so holding it here would deadlock the monitor thread.
            if timed_out:
                self._running = False
                self.on_timeout()

            # Check more frequently for responsiveness (especially in tests)
            time.sleep(0.1)

    def get_time_since_activity(self) -> float:
        """
        Get seconds since last activity.

        Returns:
            Seconds since last recorded activity
        """
        with self._lock:
            return time.time() - self.last_activity

    def reset(self) -> None:
        """Reset the activity tracker."""
        with self._lock:
            self.last_activity = time.time()
            self._save_last_activity()

    def get_remaining_time(self) -> float:
        """
        Get seconds remaining before inactivity timeout.

        Returns:
            Seconds remaining (0 if timeout exceeded)
        """
        elapsed = self.get_time_since_activity()
        remaining = self.inactivity_timeout - elapsed
        return max(0, remaining)
