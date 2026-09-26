"""Run: python tests/test_judge.py

The --judge pass with a stand-in client that returns responses in the
Messages API's documented shape (content blocks, stop_reason). No network,
no credentials: what's tested is sourced's side -- which claims are sent,
how the request is built, and above all that a verdict whose "evidence"
isn't actually in the source is thrown away.
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from sourced import judge as judge_mod
from sourced.check import CONTRADICTED, GROUNDED, UNVERIFIED, check_output
from sourced.judge import JudgeUnavailable, judge

SOURCE = ("Acme reported revenue of $56 billion for the quarter. "
          "Operating costs fell sharply after the restructuring. "
          "The board approved a new share buyback.")
OUTPUT = ("Acme reported revenue of $56 billion. "                 # grounded by string matching
          "Costs went down a lot after the reorganization. "      # paraphrase: needs the judge
          "The company raised its dividend. "                     # not in the source
          "Operating costs rose after the restructuring.")        # a flipped verb


class FakeClient:
    def __init__(self, verdicts=None, stop_reason="end_turn"):
        self.calls = []
        self.verdicts = verdicts or []
        self.stop_reason = stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        text = json.dumps({"verdicts": self.verdicts})
        return SimpleNamespace(stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="text", text=text)])


class TestJudge(unittest.TestCase):
    def setUp(self):
        self.report = check_output(OUTPUT, SOURCE)
        # The string pass decides only the first claim.
        self.assertEqual([r["status"] for r in self.report["claims"]],
                         [GROUNDED, UNVERIFIED, UNVERIFIED, UNVERIFIED])

    def test_only_undecided_claims_are_sent_with_the_source_cached(self):
        client = FakeClient()
        judge(self.report, SOURCE, client=client)
        call = client.calls[0]
        self.assertNotIn("$56 billion", call["messages"][0]["content"])  # already decided
        self.assertIn("1. Costs went down", call["messages"][0]["content"])
        self.assertIn(SOURCE, call["system"][0]["text"])
        self.assertEqual(call["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(call["model"], "claude-opus-5")
        self.assertEqual(call["fallbacks"], "default")
        self.assertEqual(call["output_config"]["format"]["type"], "json_schema")

    def test_quoted_verdicts_are_applied(self):
        client = FakeClient([
            {"claim": 1, "status": GROUNDED, "evidence": "Operating costs fell sharply after the restructuring."},
            {"claim": 2, "status": UNVERIFIED, "evidence": ""},
            {"claim": 3, "status": CONTRADICTED, "evidence": "Operating costs fell sharply"},
        ])
        judge(self.report, SOURCE, client=client)
        self.assertEqual([r["status"] for r in self.report["claims"]],
                         [GROUNDED, GROUNDED, UNVERIFIED, CONTRADICTED])
        self.assertEqual(self.report["counts"], {GROUNDED: 2, CONTRADICTED: 1, UNVERIFIED: 1})
        self.assertEqual(self.report["judge"]["decided"], 2)
        self.assertIn("Operating costs fell sharply", self.report["claims"][3]["detail"])

    def test_a_verdict_whose_quote_is_not_in_the_source_is_discarded(self):
        client = FakeClient([
            {"claim": 2, "status": GROUNDED, "evidence": "The board raised the dividend."},  # invented
            {"claim": 3, "status": GROUNDED, "evidence": ""},                                # no quote
        ])
        judge(self.report, SOURCE, client=client)
        self.assertEqual(self.report["claims"][2]["status"], UNVERIFIED)
        self.assertEqual(self.report["claims"][3]["status"], UNVERIFIED)
        self.assertEqual(self.report["judge"]["discarded"], 2)

    def test_quote_matching_tolerates_whitespace_and_curly_quotes_only(self):
        report = check_output("It said the outlook was “strong”.", 'The CEO called the outlook "strong"  today.')
        client = FakeClient([{"claim": 1, "status": GROUNDED,
                              "evidence": "called the outlook “strong” today"}])
        judge(report, 'The CEO called the outlook "strong"  today.', client=client)
        self.assertEqual(report["claims"][0]["status"], GROUNDED)

    def test_a_refusal_leaves_everything_unverified(self):
        judge(self.report, SOURCE, client=FakeClient(stop_reason="refusal"))
        self.assertTrue(self.report["judge"]["refused"])
        self.assertEqual(self.report["counts"][UNVERIFIED], 3)

    def test_nothing_undecided_means_no_request(self):
        report = check_output("Acme reported revenue of $56 billion.", SOURCE)
        client = FakeClient()
        judge(report, SOURCE, client=client)
        self.assertEqual(client.calls, [])

    def test_missing_sdk_is_a_clear_message(self):
        with mock.patch.dict(sys.modules, {"anthropic": None}):
            with self.assertRaisesRegex(JudgeUnavailable, r"sourced-evidence\[judge\]"):
                judge_mod._make_client()


if __name__ == "__main__":
    unittest.main()
