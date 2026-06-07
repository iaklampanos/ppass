"""Tests for activity tracking."""

import os
import time
import unittest
from ppass.core.activity import ActivityTracker


class TestActivityTracker(unittest.TestCase):
    """Test cases for ActivityTracker."""

    def test_initialization(self):
        """Test tracker initialization."""
        tracker = ActivityTracker(inactivity_timeout=10)
        self.assertEqual(tracker.inactivity_timeout, 10)
        self.assertFalse(tracker._running)

    def test_record_activity(self):
        """Test recording activity."""
        tracker = ActivityTracker()
        initial_time = tracker.last_activity
        
        time.sleep(0.1)
        tracker.record_activity()
        
        self.assertGreater(tracker.last_activity, initial_time)

    def test_time_since_activity(self):
        """Test time since activity calculation."""
        tracker = ActivityTracker()
        tracker.record_activity()
        
        time.sleep(0.1)
        elapsed = tracker.get_time_since_activity()
        
        self.assertGreaterEqual(elapsed, 0.1)
        self.assertLess(elapsed, 1.0)

    def test_timeout_callback(self):
        """Test timeout callback execution."""
        callback_called = {"called": False}
        
        def on_timeout():
            callback_called["called"] = True
        
        tracker = ActivityTracker(inactivity_timeout=1, on_timeout=on_timeout)
        tracker.start()
        
        # Wait for timeout + buffer for thread processing
        time.sleep(2.5)
        
        self.assertTrue(callback_called["called"])
        tracker.stop()

    def test_reload_last_activity_picks_up_external_update(self):
        """reload_last_activity re-reads the persisted timestamp from disk.

        This is what lets the long-running watcher see activity recorded by
        other ppass invocations.
        """
        tracker = ActivityTracker(tracker_id="ppass_reload_unit_test")
        try:
            # Simulate another process recording activity far in the future.
            future = tracker.last_activity + 1000
            with open(tracker._tracker_file, "w") as f:
                f.write(str(future))

            tracker.reload_last_activity()
            self.assertEqual(tracker.last_activity, future)
        finally:
            try:
                os.remove(tracker._tracker_file)
            except OSError:
                pass

    def test_reset(self):
        """Test tracker reset."""
        tracker = ActivityTracker()
        initial = tracker.last_activity

        time.sleep(0.1)
        tracker.reset()

        self.assertGreater(tracker.last_activity, initial)

    def test_activity_file_has_restricted_permissions(self):
        """The activity file is created with 0o600 permissions."""
        import stat
        tracker = ActivityTracker(tracker_id="ppass_perms_unit_test")
        tracker.record_activity()
        try:
            mode = os.stat(tracker._tracker_file).st_mode
            self.assertEqual(stat.S_IMODE(mode), 0o600)
        finally:
            try:
                os.remove(tracker._tracker_file)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
