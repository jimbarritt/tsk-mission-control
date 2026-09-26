import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tsk_mission_control import list_view, state


class DirectorySignatureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)

    def test_empty_and_missing_directory_both_give_empty_signature(self):
        self.assertEqual(list_view._directory_signature(self.directory), ())
        self.assertEqual(list_view._directory_signature(self.directory / "gone"), ())

    def test_changes_when_a_file_is_added(self):
        before = list_view._directory_signature(self.directory)
        path = self.directory / "%1.json"
        state.save(state.new(name="tsk", pane_id="%1", worktree="/x"), path)
        after = list_view._directory_signature(self.directory)
        self.assertNotEqual(before, after)

    def test_changes_when_a_tracked_file_is_rewritten(self):
        path = self.directory / "%1.json"
        state.save(state.new(name="tsk", pane_id="%1", worktree="/x"), path)
        before = list_view._directory_signature(self.directory)
        state.update(path, tokens_total=99)
        after = list_view._directory_signature(self.directory)
        self.assertNotEqual(before, after)

    def test_stable_when_nothing_changes(self):
        path = self.directory / "%1.json"
        state.save(state.new(name="tsk", pane_id="%1", worktree="/x"), path)
        first = list_view._directory_signature(self.directory)
        second = list_view._directory_signature(self.directory)
        self.assertEqual(first, second)


class MoveCursorTest(unittest.TestCase):
    def _states(self, *pane_ids):
        return [state.new(name=p, pane_id=p, worktree="/x") for p in pane_ids]

    def test_no_states_gives_no_cursor(self):
        self.assertIsNone(list_view._move_cursor([], "%1", 1))

    def test_moves_down_and_clamps_at_the_end(self):
        states = self._states("%1", "%2", "%3")
        self.assertEqual(list_view._move_cursor(states, "%1", 1), "%2")
        self.assertEqual(list_view._move_cursor(states, "%3", 1), "%3")

    def test_moves_up_and_clamps_at_the_start(self):
        states = self._states("%1", "%2", "%3")
        self.assertEqual(list_view._move_cursor(states, "%3", -1), "%2")
        self.assertEqual(list_view._move_cursor(states, "%1", -1), "%1")

    def test_unknown_cursor_moves_from_the_first_entry(self):
        states = self._states("%1", "%2")
        self.assertEqual(list_view._move_cursor(states, "%stale", 1), "%2")


class FormatTokensTest(unittest.TestCase):
    def test_small_counts_are_shown_exactly(self):
        self.assertEqual(list_view._format_tokens(0), "0")
        self.assertEqual(list_view._format_tokens(999), "999")

    def test_thousands_use_one_decimal_k(self):
        self.assertEqual(list_view._format_tokens(1_500), "1.5k")

    def test_millions_use_one_decimal_m(self):
        self.assertEqual(list_view._format_tokens(35_158_238), "35.2M")


class SpawnNewSessionPaneTest(unittest.TestCase):
    def _run_side_effect(self, list_windows_output):
        def run(cmd, **kwargs):
            if cmd[:2] == ["tmux", "list-windows"]:
                return subprocess.CompletedProcess(cmd, 0, stdout=list_windows_output)
            return subprocess.CompletedProcess(cmd, 0, stdout="%9\n")
        return run

    def test_creates_the_stash_window_when_absent(self):
        with mock.patch.object(subprocess, "run", side_effect=self._run_side_effect("")) as run:
            pane_id = list_view._spawn_new_session_pane("$0", "tsk", "/home/user/tsk")
            self.assertEqual(pane_id, "%9")
            new_window_calls = [c for c in run.call_args_list if "new-window" in c.args[0]]
            self.assertEqual(len(new_window_calls), 1)

    def test_splits_the_existing_stash_window(self):
        with mock.patch.object(
            subprocess, "run", side_effect=self._run_side_effect("mc-stash\n")
        ) as run:
            pane_id = list_view._spawn_new_session_pane("$0", "tsk", "/home/user/tsk")
            self.assertEqual(pane_id, "%9")
            split_calls = [c for c in run.call_args_list if "split-window" in c.args[0]]
            self.assertEqual(len(split_calls), 1)


if __name__ == "__main__":
    unittest.main()
