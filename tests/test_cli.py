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

    def test_batch_counts_every_record_and_reports_bad_lines(self):
        src = "Microsoft reported revenue of $56 billion for the quarter."
        lines = [json.dumps({"id": "a", "output": "Microsoft reported revenue of $56 billion.", "sources": [src]}),
                 json.dumps({"id": "b", "output": "Microsoft reported revenue of $70 billion.", "source": src}),
                 "not json"]
        path = self._write("batch.jsonl", "\n".join(lines) + "\n")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["batch", path])
        self.assertEqual(code, 1)
        self.assertIn("2 record(s): 1 grounded, 1 contradicted", out.getvalue())
        self.assertIn("line 3 skipped", err.getvalue())

    def test_multiple_source_files_are_concatenated(self):
        output = self._write("output.txt", "Microsoft reported revenue of $56 billion.")
        s1 = self._write("s1.txt", "Some unrelated background.")
        s2 = self._write("s2.txt", "Microsoft reported revenue of $56 billion.")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["check", output, s1, s2])
        self.assertEqual(code, 0)
        self.assertIn("1 grounded", buf.getvalue())

    def test_missing_source_file_is_a_clean_error_not_a_traceback(self):
        """Found by testing an actual typo'd path, the same way
        providence's malformed-JSON crash was found: a missing file used
        to raise FileNotFoundError straight out of main()."""
        output = self._write("output.txt", "A claim.")
        with self.assertRaises(SystemExit) as ctx:
            main(["check", output, str(self.dir / "nope.txt")])
        self.assertIn("no such file", str(ctx.exception))

    def test_a_directory_given_instead_of_a_file_is_a_clean_error(self):
        output = self._write("output.txt", "A claim.")
        with self.assertRaises(SystemExit) as ctx:
            main(["check", output, str(self.dir)])
        self.assertIn("is a directory", str(ctx.exception))

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
