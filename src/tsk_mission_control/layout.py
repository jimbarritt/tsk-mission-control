"""The layout command (T-03).

Run inside an existing tmux session. Splits the invoking pane into the
three-pane layout, then execs into `claude`, so the invoking pane becomes
the first Claude session's pane directly rather than a wrapper around it.

    +----------+---------------------+
    |  list    |      session        |
    |  (T-04)  |    (this pane,      |
    |          |     execs claude)   |
    +----------+---------------------+
    |         terminal (plain shell)  |
    +-----------------------------------+
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import hooks, state

TERMINAL_HEIGHT_PERCENT = 20
LIST_WIDTH_PERCENT = 25
MAIN_WINDOW_NAME = "mission-control"


def _tmux(*args: str) -> None:
    subprocess.run(["tmux", *args], check=True)


def _git_repo_name(cwd: Path) -> str | None:
    try:
        top = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return Path(top).name
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def default_session_name(cwd: Path) -> str:
    return _git_repo_name(cwd) or cwd.name


def run(name: str | None) -> int:
    if "TMUX" not in os.environ:
        print("tsk-mission-control: run this inside a tmux session", file=sys.stderr)
        return 1

    pane_id = os.environ["TMUX_PANE"]
    cwd = Path.cwd()
    session_name = name or default_session_name(cwd)

    _tmux("split-window", "-v", "-t", pane_id, "-l", f"{TERMINAL_HEIGHT_PERCENT}%")
    _tmux(
        "split-window", "-h", "-b", "-t", pane_id, "-l", f"{LIST_WIDTH_PERCENT}%",
        sys.executable, "-m", "tsk_mission_control.list_view",
    )

    # Named so T-08's prefix+v binding can return to it by name rather than
    # a hardcoded window ID: an unqualified window-name target resolves
    # within whichever session the client is currently attached to, so one
    # binding, registered once here per tmux session, works for that
    # session's own main window even if other Mission Control sessions
    # exist elsewhere on the same tmux server.
    _tmux("rename-window", "-t", pane_id, MAIN_WINDOW_NAME)
    _tmux("bind-key", "v", "select-window", "-t", MAIN_WINDOW_NAME)

    state_path = state.state_file_path(pane_id)
    state.save(state.new(name=session_name, pane_id=pane_id, worktree=str(cwd)), state_path)
    os.environ["MC_STATE_FILE"] = str(state_path)

    try:
        os.execvp("claude", ["claude", "--settings", hooks.settings_json()])
    except FileNotFoundError:
        print("tsk-mission-control: claude not found on PATH", file=sys.stderr)
        return 1
