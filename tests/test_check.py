"""Run: python tests/test_check.py"""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from sourced.check import CONTRADICTED, GROUNDED, UNVERIFIED, check_claim, check_output


class TestCheckClaim(unittest.TestCase):
    def test_claim_with_no_signals_is_unverified(self):
        r = check_claim("The company grew nicely this quarter.", "Some unrelated source text.")
        self.assertEqual(r["status"], UNVERIFIED)
        self.assertIn("no checkable", r["detail"])

    def test_number_found_verbatim_in_source_is_grounded(self):
        """Also the entity-case-insensitivity regression test: "Revenue" is
        a pseudo-entity purely because it's sentence-initial, and the
        source only has it lowercase ("Q3 revenue was..."). Case-sensitive
        entity matching used to report this real match as "missing" for no
        reason other than capitalization, dragging an otherwise-grounded
        claim down to unverified."""
        source = "Q3 revenue was $42 million, up from $38 million a year ago."
        r = check_claim("Revenue was $42 million.", source)
        self.assertEqual(r["status"], GROUNDED)

    def test_number_absent_from_source_with_no_anchor_is_unverified_not_contradicted(self):
        """No shared entity to pin the comparison on -- this can only say
        'not found', not 'the source disagrees'."""
        source = "The company had a strong quarter overall."
        r = check_claim("Revenue was $42 million.", source)
        self.assertEqual(r["status"], UNVERIFIED)

    def test_entity_present_with_a_different_number_nearby_is_contradicted(self):
        source = "Microsoft reported revenue of $56 billion for the quarter."
        r = check_claim("Microsoft reported revenue of $70 billion.", source)
        self.assertEqual(r["status"], CONTRADICTED)
        self.assertEqual(r["contradictions"][0]["entity"], "Microsoft")
        self.assertIn("56", r["contradictions"][0]["source_numbers_nearby"])

    def test_entity_present_with_the_same_number_is_grounded_not_contradicted(self):
        source = "Microsoft reported revenue of $56 billion for the quarter."
        r = check_claim("Microsoft reported revenue of $56 billion.", source)
        self.assertEqual(r["status"], GROUNDED)

    def test_quoted_phrase_present_verbatim_is_grounded(self):
        source = 'The CEO said "we exceeded every target this year."'
        r = check_claim('The CEO said "we exceeded every target this year."', source)
        self.assertEqual(r["status"], GROUNDED)

    def test_quoted_phrase_not_in_source_is_unverified(self):
        source = "The CEO discussed the results at length."
        r = check_claim('The CEO said "this was our best year ever."', source)
        self.assertEqual(r["status"], UNVERIFIED)
        self.assertIn("this was our best year ever", r["detail"])

    def test_entity_only_partially_covered_is_unverified(self):
        source = "Apple's revenue grew steadily."
        r = check_claim("Apple and Microsoft both grew revenue.", source)
        self.assertEqual(r["status"], UNVERIFIED)
        self.assertIn("Microsoft", r["detail"])


class TestCheckOutput(unittest.TestCase):
    def test_multiple_claims_are_each_checked_independently(self):
        source = "Microsoft reported revenue of $56 billion. Apple grew 8%."
        output = "Microsoft reported revenue of $56 billion. Apple grew 40%. The mood was upbeat."
        report = check_output(output, source)
        self.assertEqual(len(report["claims"]), 3)
        statuses = [c["status"] for c in report["claims"]]
        self.assertEqual(statuses, [GROUNDED, CONTRADICTED, UNVERIFIED])
        self.assertEqual(report["counts"], {"grounded": 1, "contradicted": 1, "unverified": 1})

    def test_empty_output_is_zero_claims_not_an_error(self):
        report = check_output("", "some source")
        self.assertEqual(report["claims"], [])
        self.assertEqual(report["counts"], {"grounded": 0, "contradicted": 0, "unverified": 0})


if __name__ == "__main__":
    unittest.main()
