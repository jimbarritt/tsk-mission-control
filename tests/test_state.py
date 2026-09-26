import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tsk_mission_control import state


class StateStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "%3.json"

    def test_round_trip(self):
        s = state.new(name="tsk", pane_id="%3", worktree="/home/user/tsk")
        state.save(s, self.path)

        loaded = state.load(self.path)
        self.assertEqual(loaded.name, "tsk")
        self.assertEqual(loaded.pane_id, "%3")
        self.assertEqual(loaded.worktree, "/home/user/tsk")
        self.assertFalse(loaded.status.attention)
        self.assertEqual(loaded.tokens_total, 0)
        self.assertIsNotNone(loaded.updated_at)

    def test_update_patches_one_field_without_losing_others(self):
        s = state.new(name="tsk", pane_id="%3", worktree="/home/user/tsk")
        state.save(s, self.path)

        state.update(self.path, tokens_total=42)
        loaded = state.load(self.path)
        self.assertEqual(loaded.tokens_total, 42)
        self.assertEqual(loaded.name, "tsk")

        state.update(self.path, status=state.Status(attention=True, reason="permission_prompt"))
        loaded = state.load(self.path)
        self.assertTrue(loaded.status.attention)
        self.assertEqual(loaded.status.reason, "permission_prompt")
        self.assertEqual(loaded.tokens_total, 42)

    def test_list_states_scoped_to_session_dir(self):
        env = {"XDG_STATE_HOME": self.tmp.name, "TSK_MC_TMUX_SESSION_ID": "$7"}
        with mock.patch.dict("os.environ", env):
            for pane_id in ("%1", "%2"):
                path = state.state_file_path(pane_id)
                state.save(state.new(name=pane_id, pane_id=pane_id, worktree="/x"), path)

            found = {s.pane_id for s in state.list_states()}
            self.assertEqual(found, {"%1", "%2"})

    def test_list_states_empty_when_dir_missing(self):
        env = {"XDG_STATE_HOME": self.tmp.name, "TSK_MC_TMUX_SESSION_ID": "$missing"}
        with mock.patch.dict("os.environ", env):
            self.assertEqual(state.list_states(), [])


if __name__ == "__main__":
    unittest.main()
