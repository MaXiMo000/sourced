"""Extract the checkable content out of one claim: numbers, quoted
substrings, and proper-noun-shaped phrases. These are the concrete,
matchable facts a source text either does or doesn't contain -- the part
of "grounded vs unverified" that string matching can actually answer,
without needing to understand what the sentence means.
"""
from __future__ import annotations

import re
from decimal import Decimal

# A number is an integer with optional comma-grouped thousands, an optional
# fraction (a digit is required after the dot, so a sentence-ending "42."
# stays "42"), then an optional percent or scale suffix. The lookbehind
# keeps it from starting mid-token ("v2", "Q3" and "1.5.2" aren't amounts).
#
# Every number is reduced to one canonical value, so "1,000" and "1000",
# "$56 billion" and "56B", "8%" and "8 percent" compare equal, and matching
# is by value, never by substring -- "5" must not count as found in a
# source that only says "56".
_NUMBER = re.compile(
    r'(?<![\w.])(-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)'
    r'(?:\s*(%|percent\b|per cent\b)'
    r'|\s+(thousand|million|billion|trillion)\b'
    r'|(bn|[KMB])\b)?'
)
_SCALE = {"thousand": 3, "k": 3, "million": 6, "m": 6,
          "billion": 9, "bn": 9, "b": 9, "trillion": 12}
_QUOTED = re.compile(r'"([^"]{3,})"|\'([^\']{3,})\'')
# A run of 1+ directly-adjacent capitalized words -- a cheap proper-noun
# proxy, not real named-entity recognition. A lowercase joiner breaks the
# run, so "Bank of America" comes out as "Bank" and "America": a stated
# limitation of not doing real NER.
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
    """Every number in `text`, as a canonical string: "1,200,000" ->
    "1200000", "$56 billion" -> "56000000000", "8 percent" -> "8%"."""
    return [canon for canon, _ in numbers_with_text(text)]


def numbers_with_text(text: str) -> list[tuple[str, str]]:
    """(canonical, as written) for every number -- canonical to compare,
    as-written to show a person ("56 billion", not "56000000000")."""
    found = []
    for m in _NUMBER.finditer(text):
        value = Decimal(m.group(1).replace(",", ""))
        percent, word_scale, suffix_scale = m.group(2), m.group(3), m.group(4)
        scale = (word_scale or suffix_scale or "").lower()
        if scale:
            value = value.scaleb(_SCALE[scale])
        # normalize() drops trailing zeros ("12.50" == "12.5"); format "f"
        # keeps it out of exponent notation ("5.6E+10").
        canon = format(value.normalize(), "f")
        found.append((canon + "%" if percent else canon, m.group().strip()))
    return found


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
