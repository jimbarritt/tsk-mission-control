import json
import tempfile
import unittest
from pathlib import Path

from tsk_mission_control import hooks, state


class SettingsJsonTest(unittest.TestCase):
    def test_registers_every_event_with_the_same_command(self):
        parsed = json.loads(hooks.settings_json())
        self.assertEqual(set(parsed["hooks"]), set(hooks.EVENTS))
        commands = {
            block["hooks"][0]["command"]
            for entries in parsed["hooks"].values()
            for block in entries
        }
        self.assertEqual(len(commands), 1)
        self.assertIn("tsk_mission_control.hooks", next(iter(commands)))


class HandleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "%1.json"
        state.save(state.new(name="tsk", pane_id="%1", worktree="/x"), self.path)

    def _payload(self, event: str, **extra) -> dict:
        return {
            "hook_event_name": event,
            "session_id": "abc-123",
            "transcript_path": "/tmp/transcript.jsonl",
            "cwd": "/x",
            **extra,
        }

    def test_session_start_registers_ids_without_setting_attention(self):
        hooks.handle(self._payload("SessionStart", source="startup"), self.path)
        loaded = state.load(self.path)
        self.assertEqual(loaded.claude_session_id, "abc-123")
        self.assertEqual(loaded.transcript_path, "/tmp/transcript.jsonl")
        self.assertFalse(loaded.status.attention)

    def test_notification_sets_attention_with_its_type_as_reason(self):
        hooks.handle(self._payload("Notification", notification_type="idle_prompt"), self.path)
        loaded = state.load(self.path)
        self.assertTrue(loaded.status.attention)
        self.assertEqual(loaded.status.reason, "idle_prompt")

    def test_permission_request_sets_attention(self):
        hooks.handle(self._payload("PermissionRequest", tool_name="Bash"), self.path)
        self.assertTrue(state.load(self.path).status.attention)

    def test_stop_sets_attention(self):
        hooks.handle(self._payload("Stop", stop_hook_active=False), self.path)
        self.assertTrue(state.load(self.path).status.attention)

    def test_user_prompt_submit_clears_attention(self):
        hooks.handle(self._payload("Stop"), self.path)
        hooks.handle(self._payload("UserPromptSubmit", prompt="hi"), self.path)
        self.assertFalse(state.load(self.path).status.attention)

    def test_post_tool_use_clears_attention_set_by_a_permission_request(self):
        hooks.handle(self._payload("PermissionRequest", tool_name="Bash"), self.path)
        self.assertTrue(state.load(self.path).status.attention)
        hooks.handle(self._payload("PostToolUse", tool_name="Bash"), self.path)
        self.assertFalse(state.load(self.path).status.attention)

    def test_session_end_error_sets_attention(self):
        hooks.handle(self._payload("SessionEnd", reason="error"), self.path)
        loaded = state.load(self.path)
        self.assertTrue(loaded.status.attention)
        self.assertEqual(loaded.status.reason, "session_end:error")

    def test_session_end_clean_reasons_do_not_set_attention(self):
        for reason in ("clear", "logout", "exit", "other", "prompt_input_exit"):
            with self.subTest(reason=reason):
                hooks.handle(self._payload("SessionEnd", reason=reason), self.path)
                self.assertFalse(state.load(self.path).status.attention)


class MainGuardTest(unittest.TestCase):
    def test_returns_cleanly_with_no_state_file_env_var(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MC_STATE_FILE", None)
            self.assertEqual(hooks.main(), 0)


if __name__ == "__main__":
    unittest.main()
