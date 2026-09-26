import subprocess
import unittest
from pathlib import Path
from unittest import mock

from tsk_mission_control import layout


class DefaultSessionNameTest(unittest.TestCase):
    def test_uses_git_repo_name(self):
        with mock.patch.object(subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="/home/user/tsk\n"
            )
            self.assertEqual(layout.default_session_name(Path("/home/user/tsk")), "tsk")

    def test_falls_back_to_cwd_name_outside_a_repo(self):
        with mock.patch.object(subprocess, "run") as run:
            run.side_effect = subprocess.CalledProcessError(128, ["git"])
            self.assertEqual(
                layout.default_session_name(Path("/home/user/scratch")), "scratch"
            )


if __name__ == "__main__":
    unittest.main()
