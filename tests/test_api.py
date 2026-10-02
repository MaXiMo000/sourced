"""Run: python tests/test_api.py"""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from sourced import assert_grounded, check

SOURCES = ["Microsoft reported revenue of $56 billion for the quarter.",
           "Apple grew 8% in the same period."]


class TestApi(unittest.TestCase):
    def test_check_takes_several_sources(self):
        report = check("Microsoft reported revenue of $56 billion. Apple grew 8%.", SOURCES)
        self.assertEqual(report["counts"]["grounded"], 2)

    def test_a_contradiction_fails_and_is_named(self):
        with self.assertRaises(AssertionError) as ctx:
            assert_grounded("Microsoft reported revenue of $70 billion.", SOURCES)
        self.assertIn("$70 billion", str(ctx.exception))

    def test_unverified_passes_unless_strict(self):
        assert_grounded("The mood was upbeat.", SOURCES)
        with self.assertRaises(AssertionError):
            assert_grounded("The CEO said \"best year ever\".", SOURCES, allow_unverified=False)


if __name__ == "__main__":
    unittest.main()
