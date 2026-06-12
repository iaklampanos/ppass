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
            # Simulate another process recording activity a few seconds later.
            # (Stays within the clock-skew margin; far-future values are rejected
            # by _load_last_activity — see test_load_rejects_future_timestamp.)
            updated = tracker.last_activity + 5
            with open(tracker._tracker_file, "w") as f:
                f.write(str(updated))

            tracker.reload_last_activity()
            self.assertEqual(tracker.last_activity, updated)
        finally:
            try:
                os.remove(tracker._tracker_file)
            except OSError:
                pass

    def test_save_last_activity_rejects_symlink(self):
        """_save_last_activity must not follow a symlink at the tracker path."""
        import tempfile
        tracker = ActivityTracker(tracker_id="ppass_symlink_unit_test")
        # Remove any real file that may have been created during __init__
        try:
            os.remove(tracker._tracker_file)
        except OSError:
            pass
        # Plant a symlink pointing at a harmless temp file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            target_path = tmp.name
        try:
            os.symlink(target_path, tracker._tracker_file)
            original_mtime = os.path.getmtime(target_path)
            # This must silently fail (O_NOFOLLOW raises ELOOP) rather than
            # overwriting the symlink target
            tracker._save_last_activity()
            self.assertEqual(os.path.getmtime(target_path), original_mtime,
                             "_save_last_activity followed a symlink and wrote to the target")
        finally:
            try:
                os.remove(tracker._tracker_file)
            except OSError:
                pass
            try:
                os.remove(target_path)
            except OSError:
                pass

    def test_load_rejects_future_timestamp(self):
        """A far-future timestamp is ignored so auto-unmount can't be deferred."""
        tracker = ActivityTracker(tracker_id="ppass_future_unit_test")
        try:
            with open(tracker._tracker_file, "w") as f:
                f.write(str(time.time() + 10_000))
            self.assertIsNone(tracker._load_last_activity())
        finally:
            try:
                os.remove(tracker._tracker_file)
            except OSError:
                pass

    def test_load_rejects_non_finite_timestamp(self):
        """NaN/inf are rejected: they would make the idle check never fire."""
        tracker = ActivityTracker(tracker_id="ppass_nan_unit_test")
        try:
            for bad in ("nan", "inf", "-inf"):
                with open(tracker._tracker_file, "w") as f:
                    f.write(bad)
                self.assertIsNone(
                    tracker._load_last_activity(),
                    f"{bad!r} should be rejected",
                )
        finally:
            try:
                os.remove(tracker._tracker_file)
            except OSError:
                pass

    def test_load_rejects_symlink(self):
        """_load_last_activity must not follow a symlink at the tracker path."""
        import tempfile
        tracker = ActivityTracker(tracker_id="ppass_load_symlink_unit_test")
        try:
            os.remove(tracker._tracker_file)
        except OSError:
            pass
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write(str(time.time()))
            target_path = tmp.name
        try:
            os.symlink(target_path, tracker._tracker_file)
            # O_NOFOLLOW makes the open fail (ELOOP) rather than read the target.
            self.assertIsNone(tracker._load_last_activity())
        finally:
            for p in (tracker._tracker_file, target_path):
                try:
                    os.remove(p)
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
