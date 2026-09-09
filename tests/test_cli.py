"""Run: python tests/test_cli.py

Exercises the real CLI entry point end to end -- real temp files, real
argv, real stdout capture -- not just the pure check_output() function
underneath it.
"""
from __future__ import annotations

import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from sourced.cli import main


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name: str, content: str) -> str:
        p = self.dir / name
        p.write_text(content, encoding="utf-8")
        return str(p)

    def test_exit_zero_when_nothing_contradicted(self):
        output = self._write("output.txt", "Microsoft reported revenue of $56 billion.")
        source = self._write("source.txt", "Microsoft reported revenue of $56 billion.")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["check", output, source])
        self.assertEqual(code, 0)
        self.assertIn("1 grounded", buf.getvalue())

    def test_exit_one_when_a_claim_is_contradicted(self):
        output = self._write("output.txt", "Microsoft reported revenue of $70 billion.")
        source = self._write("source.txt", "Microsoft reported revenue of $56 billion.")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["check", output, source])
        self.assertEqual(code, 1)
        self.assertIn("1 contradicted", buf.getvalue())

    def test_multiple_source_files_are_concatenated(self):
        output = self._write("output.txt", "Microsoft reported revenue of $56 billion.")
        s1 = self._write("s1.txt", "Some unrelated background.")
        s2 = self._write("s2.txt", "Microsoft reported revenue of $56 billion.")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["check", output, s1, s2])
        self.assertEqual(code, 0)
        self.assertIn("1 grounded", buf.getvalue())

    def test_json_flag_prints_the_full_report(self):
        output = self._write("output.txt", "Microsoft reported revenue of $56 billion.")
        source = self._write("source.txt", "Microsoft reported revenue of $56 billion.")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["check", output, source, "--json"])
        report = json.loads(buf.getvalue())
        self.assertEqual(report["counts"]["grounded"], 1)
        self.assertEqual(report["claims"][0]["status"], "grounded")


if __name__ == "__main__":
    unittest.main()
