"""Split LLM output into claim candidates.

A "claim" here is just a sentence -- no attempt to distinguish a factual
assertion from an opinion, a question, or a hedge ("it seems that...").
That distinction is real NLP work of its own, and is explicitly out of
scope for v1 (see README's "What this doesn't do"). Treating every
sentence as a checkable claim means the tool never silently skips
something it should have checked, at the cost of also "checking" sentences
that were never factual assertions to begin with -- those simply come back
`unverified`, which is the correct, honest answer for a sentence with
nothing in it to check.
"""
from __future__ import annotations

import re

# Split on sentence-ending punctuation followed by whitespace and what looks
# like the start of a new sentence (a capital letter, a digit, or a quote).
# Deliberately a regex, not a real sentence tokenizer (spaCy/nltk): this
# portfolio stays dependency-free where a regex handles ordinary prose well
# enough. It will over-split or under-split on abbreviations ("Dr. Smith
# arrived.") and decimal numbers at a sentence boundary -- a stated
# limitation, not a silent one; see README.
#
# The lookbehind has two alternatives, not one optional closing-quote/paren
# character, because Python's re requires a fixed-width lookbehind: a
# quantifier inside (?<=...) is a SyntaxError. Both alternatives here are
# individually fixed-width (1 char, then 2 chars) -- the quantifier just
# isn't inside the lookbehind itself.
#
# The second alternative is the fix for a real bug: American-style closing
# punctuation puts the period *inside* the quote ("four hours." not "four
# hours".), so the character immediately before the split point is the
# quote mark, not [.!?] -- the single-alternative version never matched
# there at all, silently merging two sentences into one claim.
_SENTENCE_END = re.compile(r'(?:(?<=[.!?])|(?<=[.!?][\'")\]]))\s+(?=[A-Z0-9"\'])')


def split_claims(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    # Line breaks end a claim too. LLM output puts a preamble on its own
    # line ("Here's the summary within 66 words:") and numbers list items;
    # RAGTruth showed "66" being checked as a fact about Canadian airstrikes
    # because the preamble and the first sentence were read as one claim.
    parts = [part for line in text.splitlines() for part in _SENTENCE_END.split(line)]
    return [p.strip() for p in parts if p.strip()]
