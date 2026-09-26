import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
