"""Tests for the detached inactivity-unmount watcher."""

import os
import unittest
from unittest.mock import patch, MagicMock

from ppass import watcher


class TestWatchLoop(unittest.TestCase):
    """Test cases for the watcher's core loop."""

    def test_unmounts_when_idle_past_timeout(self):
        """The loop unmounts and exits once remaining time hits zero."""
        vm = MagicMock()
        vm.is_mounted.return_value = True
        vm.activity_tracker.get_remaining_time.return_value = 0
        vm.unmount.return_value = True

        watcher._watch_loop(vm, poll_interval=0.01)

        vm.activity_tracker.reload_last_activity.assert_called()  # re-read activity
        vm.unmount.assert_called_once()

    def test_exits_without_unmount_if_already_unmounted(self):
        """If the volume is gone, the loop returns without unmounting."""
        vm = MagicMock()
        vm.is_mounted.return_value = False

        watcher._watch_loop(vm, poll_interval=0.01)

        vm.unmount.assert_not_called()

    def test_waits_then_unmounts_when_deadline_passes(self):
        """A positive remaining time defers the unmount to a later iteration."""
        vm = MagicMock()
        vm.is_mounted.return_value = True
        # First poll: still time left; second poll: expired.
        vm.activity_tracker.get_remaining_time.side_effect = [0.5, 0]
        vm.unmount.return_value = True

        with patch("ppass.watcher.time.sleep") as mock_sleep:
            watcher._watch_loop(vm, poll_interval=0.01)

        mock_sleep.assert_called_once()  # slept exactly once before expiring
        vm.unmount.assert_called_once()

    def test_retries_unmount_within_a_cycle(self):
        """A failed unmount is retried up to _UNMOUNT_ATTEMPTS times."""
        vm = MagicMock()
        # Mounted for the first cycle, then disappears so the loop can exit.
        vm.is_mounted.side_effect = [True, False]
        vm.activity_tracker.get_remaining_time.return_value = 0
        vm.unmount.return_value = False  # every attempt fails

        with patch("ppass.watcher.time.sleep"):
            watcher._watch_loop(vm, poll_interval=0.01)

        self.assertEqual(vm.unmount.call_count, watcher._UNMOUNT_ATTEMPTS)

    def test_keeps_watching_after_a_busy_cycle(self):
        """If unmount keeps failing, the loop does NOT give up early.

        It defers to the next cycle (here the volume frees up and unmounts).
        """
        vm = MagicMock()
        vm.is_mounted.return_value = True
        vm.activity_tracker.get_remaining_time.return_value = 0
        # Cycle 1: 3 failed attempts. Cycle 2: succeeds on first attempt.
        vm.unmount.side_effect = [False, False, False, True]

        with patch("ppass.watcher.time.sleep"):
            watcher._watch_loop(vm, poll_interval=0.01)

        self.assertEqual(vm.unmount.call_count, 4)


class TestWatcherLock(unittest.TestCase):
    """Test cases for the flock-based single-watcher guarantee."""

    def setUp(self):
        self.volume = "/Volumes/WatcherLockUnitTest"
        self._held = []
        self._cleanup()

    def tearDown(self):
        for f in self._held:
            try:
                f.close()
            except OSError:
                pass
        self._cleanup()

    def _cleanup(self):
        try:
            os.remove(watcher._lockfile_path(self.volume))
        except OSError:
            pass

    def test_not_running_when_unlocked(self):
        """No holder means no watcher is registered."""
        self.assertFalse(watcher.is_watcher_running(self.volume))

    def test_lock_is_exclusive_and_reusable(self):
        """Only one holder at a time; the lock frees up once released."""
        f1 = watcher._acquire_lock(self.volume)
        self._held.append(f1)
        self.assertIsNotNone(f1)

        # A second acquire fails while the first is held.
        self.assertIsNone(watcher._acquire_lock(self.volume))

        # After releasing, it can be acquired again.
        f1.close()
        self._held.remove(f1)
        f3 = watcher._acquire_lock(self.volume)
        self._held.append(f3)
        self.assertIsNotNone(f3)

    def test_is_running_reflects_held_lock(self):
        """is_watcher_running is True exactly while the lock is held."""
        f = watcher._acquire_lock(self.volume)
        self._held.append(f)
        self.assertTrue(watcher.is_watcher_running(self.volume))

        f.close()
        self._held.remove(f)
        self.assertFalse(watcher.is_watcher_running(self.volume))

    @patch("ppass.watcher.subprocess.Popen")
    def test_spawn_skipped_while_locked_then_allowed(self, mock_popen):
        """spawn_watcher no-ops while a watcher holds the lock, else launches."""
        f = watcher._acquire_lock(self.volume)
        self._held.append(f)

        self.assertFalse(watcher.spawn_watcher(self.volume, "", 300))
        mock_popen.assert_not_called()

        f.close()
        self._held.remove(f)
        self.assertTrue(watcher.spawn_watcher(self.volume, "", 300))
        mock_popen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
