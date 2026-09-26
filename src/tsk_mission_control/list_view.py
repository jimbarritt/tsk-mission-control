"""The Mission Control list view (T-04).

Shows every Claude session in this tmux session by name. Polls the state
directory rather than watching it: a poll works the same on macOS and
Linux, where an inotify-based watch would not.

No selection or key handling yet: T-05 adds those to this same loop.
"""

from __future__ import annotations

import curses
import sys
import time
from pathlib import Path

from . import state

POLL_INTERVAL_SECONDS = 0.5


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


def _draw(stdscr, states: list[state.SessionState]) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    stdscr.addstr(0, 0, "Mission Control"[: width - 1])
    if not states:
        stdscr.addstr(2, 0, "(no sessions)"[: width - 1])
    for row, session in enumerate(states, start=2):
        if row >= height:
            break
        mark = "●" if session.status.attention else "○"
        stdscr.addstr(row, 0, f"{mark} {session.name}"[: width - 1])
    stdscr.refresh()


def _loop(stdscr, session_id: str) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    directory = state.state_dir(session_id)
    last_signature = None
    while True:
        signature = _directory_signature(directory)
        if signature != last_signature:
            _draw(stdscr, state.list_states(session_id))
            last_signature = signature
        if stdscr.getch() == ord("q"):
            return
        time.sleep(POLL_INTERVAL_SECONDS)


def main() -> int:
    session_id = state.current_tmux_session_id()
    curses.wrapper(_loop, session_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
