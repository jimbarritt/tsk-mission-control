"""The Mission Control list view (T-04, T-05).

Shows every Claude session in this tmux session by name, and drives
selection and new-session creation. Polls the state directory rather than
watching it: a poll works the same on macOS and Linux, where an
inotify-based watch would not.

Switching a session into view uses `swap-pane`: the session currently
shown and the one being selected trade places, so the one leaving view
keeps running rather than being killed. A session not currently shown
lives in a hidden window, `mc-stash`, created on first use.
"""

from __future__ import annotations

import curses
import os
import subprocess
import sys
import time
from pathlib import Path

from . import layout, state

POLL_INTERVAL_SECONDS = 0.5
MC_STASH_WINDOW = "mc-stash"


def _directory_signature(directory: Path) -> tuple:
    if not directory.is_dir():
        return ()
    signature = []
    for path in sorted(directory.glob("*.json")):
        try:
            stat_result = path.stat()
        except OSError:
            continue
        signature.append((path.name, stat_result.st_mtime_ns, stat_result.st_size))
    return tuple(signature)


def _tmux_capture(args: list[str]) -> str:
    return subprocess.run(["tmux", *args], capture_output=True, text=True, check=True).stdout.strip()


def _visible_session_pane_id(window_id: str, list_pane_id: str) -> str | None:
    """The pane in this window sharing the list pane's top row: by
    construction (T-03) that is the session slot, since the terminal pane
    sits below both."""
    out = _tmux_capture(["list-panes", "-t", window_id, "-F", "#{pane_id} #{pane_top}"])
    for line in out.splitlines():
        pane_id, top = line.split()
        if top == "0" and pane_id != list_pane_id:
            return pane_id
    return None


def _stash_window_exists(session_id: str) -> bool:
    out = _tmux_capture(["list-windows", "-t", session_id, "-F", "#{window_name}"])
    return MC_STASH_WINDOW in out.splitlines()


def _spawn_new_session_pane(session_id: str, name: str, worktree: str) -> str:
    env_args = ["-e", f"MC_SESSION_NAME={name}", "-e", f"MC_WORKTREE={worktree}"]
    entrypoint = [sys.executable, "-m", "tsk_mission_control.entrypoint"]
    if _stash_window_exists(session_id):
        target = f"{session_id}:{MC_STASH_WINDOW}"
        cmd = ["split-window", "-t", target, "-c", worktree, *env_args, "-P", "-F", "#{pane_id}", "--", *entrypoint]
    else:
        cmd = [
            "new-window", "-d", "-t", session_id, "-n", MC_STASH_WINDOW, "-c", worktree,
            *env_args, "-P", "-F", "#{pane_id}", "--", *entrypoint,
        ]
    return _tmux_capture(cmd)


def _swap_into_view(pane_id: str, window_id: str, list_pane_id: str) -> None:
    visible = _visible_session_pane_id(window_id, list_pane_id)
    if visible is not None and visible != pane_id:
        subprocess.run(["tmux", "swap-pane", "-d", "-s", pane_id, "-t", visible], check=True)


def _move_cursor(states: list[state.SessionState], cursor_pane_id: str | None, direction: int) -> str | None:
    if not states:
        return None
    ids = [s.pane_id for s in states]
    try:
        index = ids.index(cursor_pane_id)
    except ValueError:
        index = 0
    index = max(0, min(len(ids) - 1, index + direction))
    return ids[index]


MAX_NAME_INPUT_LENGTH = 100


def _prompt_for_name(stdscr, default: str) -> str:
    """Read a session name on the pane's bottom row.

    Reads keys one at a time and scrolls the displayed tail of the typed
    text, rather than using curses' own `getstr`: `getstr` cannot scroll
    within a single line, so it silently stops accepting input once the
    cursor reaches the pane's right edge. A name typed in a 25%-width list
    pane would be cut to whatever fit on screen, well under
    MAX_NAME_INPUT_LENGTH, with no sign it had happened.
    """
    height, width = stdscr.getmaxyx()
    row = height - 1
    shown_default = default if len(default) <= 20 else default[:17] + "..."
    prompt = f"Name [{shown_default}]: "[: max(1, width - 1)]
    input_col = len(prompt)
    input_width = max(1, width - input_col - 1)

    buffer = ""
    curses.curs_set(1)
    stdscr.nodelay(False)
    try:
        while True:
            stdscr.move(row, 0)
            stdscr.clrtoeol()
            stdscr.addstr(row, 0, prompt)
            visible = buffer[-input_width:]
            stdscr.addstr(row, input_col, visible)
            stdscr.move(row, input_col + len(visible))
            stdscr.refresh()

            ch = stdscr.getch()
            if ch in (curses.KEY_ENTER, 10, 13):
                break
            elif ch == 27:  # Esc: cancel, keep the default
                buffer = ""
                break
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                buffer = buffer[:-1]
            elif 0 <= ch < 256 and len(buffer) < MAX_NAME_INPUT_LENGTH and chr(ch).isprintable():
                buffer += chr(ch)
    finally:
        curses.curs_set(0)
        stdscr.nodelay(True)

    text = buffer.strip()
    return text or default


def _draw(stdscr, states: list[state.SessionState], cursor_pane_id: str | None) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    stdscr.addstr(0, 0, "Mission Control"[: width - 1])
    if not states:
        stdscr.addstr(2, 0, "(no sessions)"[: width - 1])
    for row, session in enumerate(states, start=2):
        if row >= height - 1:
            break
        mark = "●" if session.status.attention else "○"
        line = f"{mark} {session.name}"[: width - 1]
        attr = curses.A_REVERSE if session.pane_id == cursor_pane_id else curses.A_NORMAL
        stdscr.addstr(row, 0, line, attr)
    stdscr.refresh()


def _loop(stdscr, session_id: str) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    directory = state.state_dir(session_id)
    list_pane_id = os.environ["TMUX_PANE"]
    window_id = _tmux_capture(["display-message", "-p", "#{window_id}"])

    last_signature = None
    states: list[state.SessionState] = []
    cursor_pane_id: str | None = None

    while True:
        signature = _directory_signature(directory)
        if signature != last_signature:
            states = state.list_states(session_id)
            if states and cursor_pane_id not in {s.pane_id for s in states}:
                cursor_pane_id = states[0].pane_id
            _draw(stdscr, states, cursor_pane_id)
            last_signature = signature

        ch = stdscr.getch()
        if ch == ord("q"):
            return
        elif ch in (ord("j"), curses.KEY_DOWN):
            cursor_pane_id = _move_cursor(states, cursor_pane_id, 1)
            _draw(stdscr, states, cursor_pane_id)
        elif ch in (ord("k"), curses.KEY_UP):
            cursor_pane_id = _move_cursor(states, cursor_pane_id, -1)
            _draw(stdscr, states, cursor_pane_id)
        elif ch == ord("n"):
            default_name = layout.default_session_name(Path.cwd())
            name = _prompt_for_name(stdscr, default_name)
            worktree = str(Path.cwd())
            new_pane_id = _spawn_new_session_pane(session_id, name, worktree)
            _swap_into_view(new_pane_id, window_id, list_pane_id)
            cursor_pane_id = new_pane_id
            last_signature = None
        elif ch in (curses.KEY_ENTER, 10, 13):
            if cursor_pane_id is not None:
                _swap_into_view(cursor_pane_id, window_id, list_pane_id)
            last_signature = None

        time.sleep(POLL_INTERVAL_SECONDS)


def main() -> int:
    session_id = state.current_tmux_session_id()
    curses.wrapper(_loop, session_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
