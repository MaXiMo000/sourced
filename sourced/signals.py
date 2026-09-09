"""Extract the checkable content out of one claim: numbers, quoted
substrings, and proper-noun-shaped phrases. These are the concrete,
matchable facts a source text either does or doesn't contain -- the part
of "grounded vs unverified" that string matching can actually answer,
without needing to understand what the sentence means.
"""
from __future__ import annotations

import re

# The fractional part requires a digit after the dot, not just an optional
# dot -- `\.?\d*` alone would swallow a following sentence period into the
# match ("42." at the end of a sentence reading as the number "42." instead
# of "42"), a real bug caught by testing this against ordinary prose, not
# synthetic numbers-only input.
_NUMBER = re.compile(r'-?\d[\d,]*(?:\.\d+)?%?')
_QUOTED = re.compile(r'"([^"]{3,})"|\'([^\']{3,})\'')
# A run of 1+ capitalized words -- a cheap proper-noun/entity proxy, not real
# named-entity recognition. Multi-word runs ("Bank of America" -- capitalized
# words joined by lowercase function words still read as one run since the
# regex only requires the *first* letter of each word to be uppercase and
# skips over up to one lowercase joiner... actually it doesn't: this simple
# version only chains directly-adjacent capitalized words. "Bank of America"
# would be seen as two separate entities, "Bank" and "America" -- a real,
# stated limitation of not doing real NER, not a bug to silently paper over.
_PROPER_NOUN = re.compile(r'\b[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)*\b')

# Common capitalized function words that are never an entity on their own
# (they're excluded even mid-sentence, e.g. "and The company" -- "The" is
# still not a proper noun there). This is the only filter single-word
# candidates get; see proper_nouns()'s docstring for why sentence position
# isn't used to filter them too.
_STOPWORD_CAPS = {
    "The", "A", "An", "This", "That", "These", "Those", "It", "In", "On",
    "At", "For", "As", "Is", "Was", "Were", "There", "Here", "But", "And",
}


def numbers(text: str) -> list[str]:
    return [m.group().replace(",", "") for m in _NUMBER.finditer(text)]


def quotes(text: str) -> list[str]:
    return [m.group(1) or m.group(2) for m in _QUOTED.finditer(text)]


def proper_nouns(text: str) -> list[str]:
    """Multi-word capitalized runs are kept unconditionally (rarely a false
    positive). A single capitalized word is kept unless it's a common
    capitalized function word (the stoplist) -- deliberately NOT excluded
    just for being sentence-initial: "Microsoft reported revenue of $70
    billion" is exactly the shape this tool most needs to anchor a
    contradiction check on, and Microsoft-as-subject is sentence-initial in
    ordinary prose far more often than not. The real cost is the flip side:
    an ordinary sentence-initial common noun ("Revenue grew...") gets
    treated as a pseudo-entity too. That's an accepted, stated trade --
    it only ever contributes to a *coverage* check ("Revenue" trivially
    tends to appear in a source that's also about revenue), and it does
    not on its own manufacture a contradiction the way a false anchor with
    a genuinely different number nearby would.
    """
    found = []
    for m in _PROPER_NOUN.finditer(text):
        phrase = m.group()
        if " " in phrase or phrase not in _STOPWORD_CAPS:
            found.append(phrase)
    return found
