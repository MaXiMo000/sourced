"""Run: python tests/test_signals.py"""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from sourced import signals


class TestNumbers(unittest.TestCase):
    def test_plain_integer(self):
        self.assertEqual(signals.numbers("Revenue was 42."), ["42"])

    def test_decimal_and_percent(self):
        self.assertEqual(signals.numbers("Grew 12.5% this quarter."), ["12.5%"])

    def test_comma_thousands_separator_is_normalized(self):
        self.assertEqual(signals.numbers("Sold 1,200,000 units."), ["1200000"])

    def test_negative_number(self):
        self.assertEqual(signals.numbers("Margin fell -3.2%."), ["-3.2%"])

    def test_scale_words_and_suffixes_reduce_to_the_same_value(self):
        self.assertEqual(signals.numbers("$56 billion"), ["56000000000"])
        self.assertEqual(signals.numbers("56B"), ["56000000000"])
        self.assertEqual(signals.numbers("56bn"), ["56000000000"])
        self.assertEqual(signals.numbers("56,000 million"), ["56000000000"])
        self.assertEqual(signals.numbers("2.5K"), ["2500"])

    def test_percent_word_equals_percent_sign(self):
        self.assertEqual(signals.numbers("up 8 percent"), ["8%"])
        self.assertEqual(signals.numbers("up 8%"), ["8%"])

    def test_trailing_zeros_do_not_change_the_value(self):
        self.assertEqual(signals.numbers("12.50"), signals.numbers("12.5"))

    def test_digits_inside_identifiers_are_not_amounts(self):
        self.assertEqual(signals.numbers("Q3 results for v2 of GPT4"), [])

    def test_as_written_text_is_kept_for_display(self):
        self.assertEqual(signals.numbers_with_text("Revenue hit 56 billion."),
                         [("56000000000", "56 billion")])

    def test_no_numbers(self):
        self.assertEqual(signals.numbers("Revenue grew nicely."), [])


class TestQuotes(unittest.TestCase):
    def test_double_quoted_phrase(self):
        self.assertEqual(signals.quotes('The CEO called it "a record quarter."'),
                          ["a record quarter."])

    def test_single_quoted_phrase(self):
        self.assertEqual(signals.quotes("She called it 'a turning point'."),
                          ["a turning point"])

    def test_short_quotes_under_three_chars_are_ignored(self):
        """A stray apostrophe pair around one letter isn't a quoted claim
        worth checking -- e.g. a possessive or a contraction fragment."""
        self.assertEqual(signals.quotes("It's 'a' small win."), [])

    def test_no_quotes(self):
        self.assertEqual(signals.quotes("Revenue grew 12%."), [])


class TestProperNouns(unittest.TestCase):
    def test_lowercase_joiner_splits_a_real_multiword_entity(self):
        """Documented limitation, not a bug: real NER would see one entity,
        'Bank of America'. This regex only chains directly-adjacent
        capitalized words, so 'of' breaks the chain -- 'Bank' (sentence-
        initial, so excluded) and 'America' (kept) come out separately."""
        self.assertEqual(signals.proper_nouns("Bank of America reported earnings."),
                          ["Bank", "America"])

    def test_adjacent_capitalized_words_do_chain(self):
        self.assertEqual(signals.proper_nouns("It involved New York City directly."),
                          ["New York City"])

    def test_sentence_initial_subject_is_kept_as_a_candidate_entity(self):
        """Deliberate, not a miss: 'Microsoft reported X' is exactly the
        subject-first shape a contradiction check needs to anchor on, and
        excluding anything sentence-initial would silently drop it. The
        real cost -- an ordinary sentence-initial common noun like
        'Revenue' also becomes a pseudo-entity -- is accepted and
        documented in signals.py, not hidden."""
        self.assertEqual(signals.proper_nouns("Revenue grew 12% in Q3."), ["Revenue", "Q3"])

    def test_stopword_caps_excluded_even_sentence_initial(self):
        self.assertEqual(signals.proper_nouns("The company grew 12% in Q3."), ["Q3"])

    def test_midsentence_single_capitalized_word_is_kept(self):
        self.assertIn("Microsoft", signals.proper_nouns("The deal involved Microsoft directly."))

    def test_stopword_caps_excluded_even_midsentence(self):
        self.assertNotIn("The", signals.proper_nouns("It grew, and The company noted it."))

    def test_no_entities(self):
        self.assertEqual(signals.proper_nouns("revenue grew twelve percent"), [])


if __name__ == "__main__":
    unittest.main()
