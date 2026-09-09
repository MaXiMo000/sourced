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
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'])')


def split_claims(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = _SENTENCE_END.split(text)
    return [p.strip() for p in parts if p.strip()]
