"""Claude Code hooks (T-06).

Two roles in one module: build the `--settings` JSON passed to `claude` at
launch (by layout.py and entrypoint.py), and act as the hook command that
JSON registers, updating a session's state file as Claude Code reports
lifecycle events.

Passing `--settings` on the `claude` command line, rather than writing
into a settings file, scopes these hooks to Mission Control's own
launches: nothing here touches the user's global Claude Code settings,
and the hooks never run for a `claude` invocation started any other way.

Event names, and the fields each hook payload carries, were confirmed
directly against the installed CLI (`cli.js`, Claude Code 2.1.283), not
from documentation: `hook_event_name`, `session_id` and `transcript_path`
are on every payload; `Notification` carries `notification_type`
(`permission_prompt`, `idle_prompt`, among others); `SessionEnd` carries
`reason`, one of `clear`, `logout`, `exit`, `other`, `prompt_input_exit`,
`error`. There is no separate event for a mid-turn API error that leaves
the session running, and no event fires when a human approves a pending
permission.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import state

EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "Notification",
    "PermissionRequest",
    "PostToolUse",
    "Stop",
    "SessionEnd",
)

# The only SessionEnd reason that means the session ended abnormally.
# Every other reason (clear, exit, logout, other, prompt_input_exit) is a
# clean end and needs no attention.
SESSION_END_ATTENTION_REASONS = {"error"}


def settings_json() -> str:
    command = f"{sys.executable} -m tsk_mission_control.hooks"
    hooks_block = {event: [{"hooks": [{"type": "command", "command": command}]}] for event in EVENTS}
    return json.dumps({"hooks": hooks_block})


def _status_change(payload: dict) -> state.Status | None:
    event = payload.get("hook_event_name")

    if event in ("UserPromptSubmit", "PostToolUse"):
        # A submitted prompt, or a tool completing, both mean the session
        # moved past whatever last needed a look. PostToolUse fires after
        # every tool call, including one just approved by a human at a
        # PermissionRequest: nothing else fires on that approval itself, so
        # clearing here is what turns "needs attention" off again.
        return state.Status(attention=False)
    if event == "Notification":
        return state.Status(attention=True, reason=payload.get("notification_type"))
    if event == "PermissionRequest":
        return state.Status(attention=True, reason="permission_request")
    if event == "Stop":
        return state.Status(attention=True, reason="stop")
    if event == "SessionEnd":
        reason = payload.get("reason")
        if reason in SESSION_END_ATTENTION_REASONS:
            return state.Status(attention=True, reason=f"session_end:{reason}")
    return None


def handle(payload: dict, path: Path) -> None:
    changes: dict = {
        "claude_session_id": payload.get("session_id"),
        "transcript_path": payload.get("transcript_path"),
    }
    status = _status_change(payload)
    if status is not None:
        changes["status"] = status
    state.update(path, **changes)


def main() -> int:
    path_str = os.environ.get("MC_STATE_FILE")
    if not path_str:
        return 0

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    path = Path(path_str)
    if not path.exists():
        return 0

    try:
        handle(payload, path)
    except Exception:
        # A hook must never block or clutter a Claude Code session by
        # failing loudly. Losing one status update is cheap; the next
        # hook call carries the same common fields anyway.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
