"""Token totals (T-07).

Sums the usage records in a Claude Code transcript file. Confirmed
directly against a real transcript, not from documentation: a streamed
response writes several JSONL lines for the same assistant message, each
repeating that message's usage totals verbatim, so a message counts once,
by its id. A `cost-state` entry also carries token totals, but it is a
one-off snapshot written partway through a session (found at line 84 of
1101 in the transcript checked), not a running total kept current to the
end of the file, so it cannot stand in for this.

TranscriptTokenCounter reads incrementally, from a saved byte offset,
rather than re-parsing the whole file on every poll tick: cheap for a
list view that refreshes repeatedly through a long session. A read stops
at the last complete line, so a transcript caught mid-write (an assistant
message still streaming) leaves its partial trailing line for the next
read to pick up, rather than treating a truncated line as garbage and
skipping the bytes that complete it.
"""

from __future__ import annotations

import json
from pathlib import Path


class TranscriptTokenCounter:
    def __init__(self) -> None:
        self._byte_offset = 0
        self._seen_message_ids: set[str] = set()
        self._total = 0

    def total(self, transcript_path: str) -> int:
        try:
            with Path(transcript_path).open("rb") as f:
                f.seek(self._byte_offset)
                chunk = f.read()
        except OSError:
            return self._total

        lines = chunk.split(b"\n")
        complete_lines = lines[:-1]
        for raw_line in complete_lines:
            self._consume(raw_line.decode("utf-8", errors="replace"))
        self._byte_offset += sum(len(line) + 1 for line in complete_lines)
        return self._total

    def _consume(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            return
        message = entry.get("message")
        if not isinstance(message, dict):
            return
        message_id = message.get("id")
        if message_id is None or message_id in self._seen_message_ids:
            return
        usage = message.get("usage")
        if not isinstance(usage, dict):
            return
        self._seen_message_ids.add(message_id)
        self._total += (
            usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
            + usage.get("output_tokens", 0)
        )
