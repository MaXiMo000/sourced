"""Run: python tests/test_claims.py"""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from sourced.claims import split_claims


class TestSplitClaims(unittest.TestCase):
    def test_empty_text_is_no_claims(self):
        self.assertEqual(split_claims(""), [])
        self.assertEqual(split_claims("   "), [])

    def test_single_sentence_is_one_claim(self):
        self.assertEqual(split_claims("Revenue grew 12% in Q3."),
                          ["Revenue grew 12% in Q3."])

    def test_multiple_sentences_split_on_terminal_punctuation(self):
        text = "Revenue grew 12% in Q3. Costs fell slightly. Margins improved."
        self.assertEqual(split_claims(text), [
            "Revenue grew 12% in Q3.",
            "Costs fell slightly.",
            "Margins improved.",
        ])

    def test_question_marks_and_exclamations_also_split(self):
        text = "Did revenue grow? Yes, by 12%! That beat expectations."
        self.assertEqual(len(split_claims(text)), 3)

    def test_a_decimal_number_does_not_split_mid_sentence(self):
        """3.14 is not two sentences -- the split only fires when a capital,
        digit, or quote follows the punctuation+space, and a lowercase
        continuation (or no space at all, as in a decimal) doesn't count."""
        text = "Pi is approximately 3.14 and shows up everywhere."
        self.assertEqual(split_claims(text), [text])

    def test_known_limitation_abbreviations_over_split(self):
        """Documented, not hidden: 'Dr. Smith' reads as two sentences,
        since this is a regex, not a real tokenizer that knows abbreviations."""
        text = "Dr. Smith signed the report."
        self.assertEqual(len(split_claims(text)), 2)

    def test_a_period_inside_a_closing_quote_still_splits(self):
        """Real bug, found live: American-style punctuation puts the period
        *inside* the quote ("four hours." not "four hours".), so the
        character right before the split point is the quote mark, not
        [.!?] -- the original lookbehind only ever checked for [.!?]
        directly, so this silently merged two claims into one."""
        text = 'The report said the outage lasted "four hours." The team resolved it by noon.'
        self.assertEqual(split_claims(text), [
            'The report said the outage lasted "four hours."',
            "The team resolved it by noon.",
        ])

    def test_a_period_outside_a_closing_quote_still_splits(self):
        """The other quoting convention already worked (the period itself
        sits right before the space) -- pinned so a future regex change
        can't fix one convention by breaking the other."""
        text = 'The report said the outage lasted "four hours". The team resolved it by noon.'
        self.assertEqual(split_claims(text), [
            'The report said the outage lasted "four hours".',
            "The team resolved it by noon.",
        ])

    def test_a_period_inside_a_closing_paren_still_splits(self):
        text = "She said it works (allegedly.) Then it broke."
        self.assertEqual(split_claims(text), [
            "She said it works (allegedly.)",
            "Then it broke.",
        ])


if __name__ == "__main__":
    unittest.main()
