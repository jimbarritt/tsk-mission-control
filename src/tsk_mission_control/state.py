"""The session state store.

One JSON file per Claude Code session, keyed by the tmux pane it runs in.
The Mission Control app and the Claude Code hooks (T-06) both read and
write these files, so writes go through a lock and a temp-file rename:
a Notification hook and a Stop hook can fire close together on the same
file.
"""

from __future__ import annotations

import dataclasses
import fcntl
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def xdg_state_home() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")


def current_tmux_session_id() -> str:
    """The tmux session ID (e.g. '$3') Mission Control is running in.

    Read from $TSK_MC_TMUX_SESSION_ID when set, so a hook or a test can pin
    it without shelling out to tmux. Otherwise asks the tmux server directly,
    which only works from inside a pane that belongs to that session.
    """
    override = os.environ.get("TSK_MC_TMUX_SESSION_ID")
    if override:
        return override
    result = subprocess.run(
        ["tmux", "display-message", "-p", "#{session_id}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def state_dir(tmux_session_id: str | None = None) -> Path:
    session_id = tmux_session_id or current_tmux_session_id()
    return xdg_state_home() / "tsk-mission-control" / session_id


def state_file_path(pane_id: str, tmux_session_id: str | None = None) -> Path:
    return state_dir(tmux_session_id) / f"{pane_id}.json"


@dataclasses.dataclass
class Status:
    attention: bool = False
    reason: str | None = None
    since: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Status":
        return cls(
            attention=bool(data.get("attention", False)),
            reason=data.get("reason"),
            since=data.get("since"),
        )


@dataclasses.dataclass
class SessionState:
    name: str
    pane_id: str
    worktree: str
    claude_session_id: str | None = None
    transcript_path: str | None = None
    status: Status = dataclasses.field(default_factory=Status)
    tokens_total: int = 0
    schema_version: int = SCHEMA_VERSION
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        data["status"] = self.status.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        return cls(
            name=data["name"],
            pane_id=data["pane_id"],
            worktree=data["worktree"],
            claude_session_id=data.get("claude_session_id"),
            transcript_path=data.get("transcript_path"),
            status=Status.from_dict(data.get("status", {})),
            tokens_total=int(data.get("tokens_total", 0)),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            updated_at=data.get("updated_at"),
        )


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new(name: str, pane_id: str, worktree: str) -> SessionState:
    return SessionState(name=name, pane_id=pane_id, worktree=worktree, updated_at=_now())


def load(path: Path) -> SessionState:
    with path.open("r", encoding="utf-8") as f:
        return SessionState.from_dict(json.load(f))


def save(state: SessionState, path: Path) -> None:
    """Write state to path, holding an exclusive lock for the duration.

    Locks a sibling `.lock` file rather than the target itself, so the
    rename below never has to happen while the file it replaces is locked.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    state.updated_at = _now()
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2)
                f.write("\n")
            os.replace(tmp_path, path)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def update(path: Path, **changes: Any) -> SessionState:
    """Read-modify-write path under the same lock, so a hook can patch one
    field without racing a concurrent writer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            state = load(path) if path.exists() else None
            if state is None:
                raise FileNotFoundError(path)
            for key, value in changes.items():
                setattr(state, key, value)
            state.updated_at = _now()
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2)
                f.write("\n")
            os.replace(tmp_path, path)
            return state
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def list_states(tmux_session_id: str | None = None) -> list[SessionState]:
    directory = state_dir(tmux_session_id)
    if not directory.is_dir():
        return []
    states = []
    for entry in sorted(directory.glob("*.json"), key=_pane_sort_key):
        try:
            states.append(load(entry))
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return states


def _pane_sort_key(path: Path) -> int:
    """Sort by the pane ID's numeric value, not lexicographically: '%2' must
    come before '%10', which string sorting would get backwards."""
    try:
        return int(path.stem.lstrip("%"))
    except ValueError:
        return -1
