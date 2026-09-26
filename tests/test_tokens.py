import json
import tempfile
import unittest
from pathlib import Path

from tsk_mission_control.tokens import TranscriptTokenCounter


def _assistant_line(message_id: str, usage: dict, is_sidechain=False) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "isSidechain": is_sidechain,
            "message": {"id": message_id, "usage": usage},
        }
    )


USAGE_A = {
    "input_tokens": 2,
    "cache_creation_input_tokens": 100,
    "cache_read_input_tokens": 0,
    "output_tokens": 50,
}
USAGE_B = {
    "input_tokens": 3,
    "cache_creation_input_tokens": 10,
    "cache_read_input_tokens": 100,
    "output_tokens": 20,
}


class TranscriptTokenCounterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "transcript.jsonl"

    def _write(self, text: str) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(text)

    def test_counts_a_single_message_once_despite_streamed_repeats(self):
        # A real transcript writes the same message id several times, with
        # identical usage each time, as a response streams.
        line = _assistant_line("msg_1", USAGE_A) + "\n"
        self._write(line * 3)

        counter = TranscriptTokenCounter()
        self.assertEqual(counter.total(str(self.path)), 152)

    def test_sums_across_distinct_messages(self):
        self._write(_assistant_line("msg_1", USAGE_A) + "\n")
        self._write(_assistant_line("msg_2", USAGE_B) + "\n")

        counter = TranscriptTokenCounter()
        self.assertEqual(counter.total(str(self.path)), 152 + 133)

    def test_incremental_reads_do_not_double_count(self):
        self._write(_assistant_line("msg_1", USAGE_A) + "\n")
        counter = TranscriptTokenCounter()
        self.assertEqual(counter.total(str(self.path)), 152)

        self._write(_assistant_line("msg_1", USAGE_A) + "\n")  # a streamed repeat
        self._write(_assistant_line("msg_2", USAGE_B) + "\n")  # genuinely new
        self.assertEqual(counter.total(str(self.path)), 152 + 133)

    def test_a_partial_trailing_line_is_not_consumed_until_complete(self):
        self._write(_assistant_line("msg_1", USAGE_A) + "\n")
        partial = _assistant_line("msg_2", USAGE_B)
        self._write(partial[: len(partial) // 2])  # no trailing newline: mid-write

        counter = TranscriptTokenCounter()
        self.assertEqual(counter.total(str(self.path)), 152)

        self._write(partial[len(partial) // 2 :] + "\n")  # the write completes
        self.assertEqual(counter.total(str(self.path)), 152 + 133)

    def test_sidechain_entries_are_excluded(self):
        self._write(_assistant_line("msg_1", USAGE_A, is_sidechain=True) + "\n")
        counter = TranscriptTokenCounter()
        self.assertEqual(counter.total(str(self.path)), 0)

    def test_missing_file_gives_zero(self):
        counter = TranscriptTokenCounter()
        self.assertEqual(counter.total(str(self.path)), 0)

    def test_non_assistant_and_malformed_lines_are_skipped(self):
        self._write("not json at all\n")
        self._write(json.dumps({"type": "user"}) + "\n")
        self._write(_assistant_line("msg_1", USAGE_A) + "\n")

        counter = TranscriptTokenCounter()
        self.assertEqual(counter.total(str(self.path)), 152)


if __name__ == "__main__":
    unittest.main()
