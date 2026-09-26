"""Registers a freshly spawned pane's Claude session, then execs claude.

Run as a new pane's command, with MC_SESSION_NAME and MC_WORKTREE set in
its environment. Reads its own pane ID from $TMUX_PANE, which tmux always
sets for a pane's process, so the caller that spawns the pane never needs
to know the pane ID in advance: it is only assigned once the pane exists.
"""

from __future__ import annotations

import os
import sys

from . import state


def main() -> int:
    pane_id = os.environ["TMUX_PANE"]
    name = os.environ["MC_SESSION_NAME"]
    worktree = os.environ["MC_WORKTREE"]

    path = state.state_file_path(pane_id)
    state.save(state.new(name=name, pane_id=pane_id, worktree=worktree), path)
    os.environ["MC_STATE_FILE"] = str(path)

    try:
        os.execvp("claude", ["claude"])
    except FileNotFoundError:
        print("tsk-mission-control: claude not found on PATH", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
