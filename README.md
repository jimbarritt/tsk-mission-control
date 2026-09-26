# tsk-mission-control

A tmux control panel for Claude Code sessions. Replicates the Claude app's
layout, native in the terminal: a list of running sessions on the left, the
selected session on the right, and a plain terminal across the bottom.

Standalone. No dependency on the `tsk` binary or its daemon. It uses tmux,
Claude Code hooks, and Claude Code's own transcript files.

Phase one, macOS only. Read on Linux for development, since Claude Code's
cloud sandbox runs there; a Linux run is not a supported target.

## Requirements

- tmux 3.4 or later
- Python 3.9 or later
- Claude Code CLI 2.1.283 or later
- [pipx](https://pipx.pypa.io/), to install this package on `PATH`
- nvim, for the T-08 shortcut

## Install

```bash
pipx install --editable .
```

This puts the `tsk-mission-control` command on `PATH`, in its own isolated
virtual environment, without touching the system Python or any project
virtual environment. `--editable` means a `git pull` in this repo takes
effect the next time the command runs, with no reinstall step.

## Usage

```bash
tsk-mission-control [name]
```

Run inside a new tmux session. Builds the three-pane layout and starts the
first Claude Code session, named after the current git repository unless
`name` is given.

Not yet built past this skeleton. The task breakdown and status live in the
`jimbarritt/tsk` repository's mission ledger, mission M-BOOT-06, since this
repository carries no tsk knowledge of its own.

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

No test dependency beyond the standard library.
