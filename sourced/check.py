"""Check one claim against source text: grounded, contradicted, or
unverified -- never a blended trust score. See README for exactly what
each status means, and what this deliberately does not attempt (semantic
entailment, paraphrase matching -- see "What this doesn't do").

Evidence has to be *local*. The first version grounded a claim when each
of its numbers and names appeared anywhere in the source; checked against
the 73 KB Wikipedia article on PostgreSQL, "Stonebraker returned to
Berkeley in 1991" came back grounded because 1991 is in the article --
about something else -- and the sentence that matters says 1985. Now the
signals must sit together in one passage (a few consecutive sentences),
alongside most of the claim's own words, and a negation on one side only
("used Ingres's ideas but not its code") blocks a grounded verdict.
"""
from __future__ import annotations

import re

from . import signals
from .claims import split_claims

GROUNDED, CONTRADICTED, UNVERIFIED = "grounded", "contradicted", "unverified"

PASSAGE_SENTENCES = 3
# Share of the claim's content words the passage must also contain. Names
# and numbers pin *what* a claim is about; these words are what it says
# about them ("reused the code" vs "used the ideas").
CONTENT_MIN = 0.6

_CITATION = re.compile(r"\[\d+\]")
_WORD = re.compile(r"[a-z][a-z0-9'-]*[a-z0-9]|[a-z]")
_NEGATIONS = {"not", "no", "never", "none", "nor", "without", "cannot", "neither"}
_STOP = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at", "by", "for",
    "with", "from", "as", "is", "was", "were", "are", "be", "been", "being", "has",
    "have", "had", "it", "its", "this", "that", "these", "those", "their", "there",
    "which", "who", "whom", "whose", "than", "then", "also", "into", "over", "under",
    "about", "after", "before", "per", "via", "so", "such", "some", "any", "all",
    "both", "each", "more", "most", "very", "can", "could", "would", "should", "will",
    "may", "might", "do", "does", "did", "he", "she", "they", "we", "you", "i", "his",
    "her", "our", "your", "them", "him", "up", "out", "said", "says", "say",
}


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _content(text: str) -> set[str]:
    return {w for w in _words(text) if w not in _STOP and w not in _NEGATIONS and len(w) > 2}


def _negated(text: str) -> bool:
    lower = text.lower()
    return bool(_words(lower) & _NEGATIONS) or "n't" in lower


def _passages(source: str) -> list[tuple[str, list[str]]]:
    sentences = split_claims(source) or [source]
    width = min(PASSAGE_SENTENCES, len(sentences))
    return [(" ".join(sentences[i:i + width]), sentences[i:i + width])
            for i in range(len(sentences) - width + 1)]


def _signals_detail(nums, ents, quoted) -> dict:
    return {"numbers": nums, "entities": ents, "quotes": quoted}


def check_claim(claim: str, source: str) -> dict:
    claim_nums = signals.numbers_with_text(claim)
    nums = [canon for canon, _ in claim_nums]
    ents = signals.proper_nouns(claim)
    quoted = signals.quotes(claim)
    sig = _signals_detail(nums, ents, quoted)

    if not nums and not ents and not quoted:
        return {"claim": claim, "status": UNVERIFIED,
                "detail": "no checkable numbers, quoted text, or capitalized entities in this claim",
                "signals": sig}

    words = _content(claim)
    claim_negated = _negated(claim)
    best = None  # the passage that explains the most of this claim
    candidates = []
    for text, sentences in _passages(source):
        lower = text.lower()
        p_nums = set(signals.numbers(text))
        missing_nums = [n for n in nums if n not in p_nums]
        # Case-insensitive: "Revenue" is capitalized only by position, and
        # most source text has it lowercase mid-sentence.
        missing_ents = [e for e in ents if e.lower() not in lower]
        missing_quotes = [q for q in quoted if q not in text]
        found = _words(text)
        cover = len(words & found) / len(words) if words else 1.0
        # The one sentence in the passage that best matches, for negation:
        # a "not" three sentences away says nothing about this claim.
        closest = max(sentences, key=lambda s: len(words & _words(s)))
        cand = {"text": text, "missing_nums": missing_nums, "missing_ents": missing_ents,
                "missing_quotes": missing_quotes, "cover": cover, "p_nums": p_nums,
                "negation_differs": _negated(closest) != claim_negated}
        rank = (-(len(missing_nums) + len(missing_ents) + len(missing_quotes)),
                not cand["negation_differs"], cover)
        cand["rank"] = rank
        candidates.append(cand)
        if best is None or rank > best["rank"]:
            best = cand
        if not (missing_nums or missing_ents or missing_quotes) and cover >= CONTENT_MIN \
                and not cand["negation_differs"]:
            # A single capitalized word that only starts the sentence
            # ("Operating costs rose...") is a pseudo-entity: finding it says
            # nothing about the claim.
            first_word = claim.lstrip().split(" ", 1)[0].strip('"\'(')
            if not (nums or quoted or any(" " in e or e != first_word for e in ents)):
                return {"claim": claim, "status": UNVERIFIED,
                        "detail": ("only the sentence's first word matched the source -- no number, "
                                   "quote or name to check the claim itself against"),
                        "signals": sig}
            return {"claim": claim, "status": GROUNDED,
                    "detail": ("every number, name and quoted phrase in this claim appears in one "
                               "passage of the source, with most of what it says about them"),
                    "signals": sig}

    # Contradicted: a passage about the same thing -- every name in the
    # claim, most of its words -- states a different number, and not the
    # claim's. Needs a real anchor (at least one name), so two unrelated
    # numbers in a long document never make a contradiction.
    if ents and nums:
        about = [c for c in candidates
                 if not c["missing_ents"] and c["missing_nums"] and c["p_nums"]
                 and c["cover"] >= CONTENT_MIN]
        if about:
            c = max(about, key=lambda c: c["cover"])
            # What the passage says near the names, minus citation markers
            # ("[27]") -- evidence a person can read, not every digit.
            text = _CITATION.sub(" ", c["text"])
            said = []
            for ent in ents:
                for m in re.finditer(re.escape(ent), text, re.I):
                    for _, t in signals.numbers_with_text(text[max(0, m.start() - 80): m.end() + 80]):
                        if t not in said:
                            said.append(t)
            said = said or [t for _, t in signals.numbers_with_text(text)]
            first_missing = next(t for canon, t in claim_nums if canon in c["missing_nums"])
            return {"claim": claim, "status": CONTRADICTED,
                    "detail": (f"claims {first_missing} about {', '.join(ents)}, but the source's "
                               f"passage about them says {said}"),
                    "signals": sig,
                    "contradictions": [{"claim_number": first_missing, "entity": ents[0],
                                        "source_numbers_nearby": said}]}

    if best["missing_nums"] or best["missing_ents"] or best["missing_quotes"]:
        total = len(nums) + len(ents) + len(quoted)
        missing = len(best["missing_nums"]) + len(best["missing_ents"]) + len(best["missing_quotes"])
        detail = (f"{missing}/{total} signal(s) not found together in any one passage -- "
                  f"numbers {best['missing_nums']}, entities {best['missing_ents']}, "
                  f"quotes {best['missing_quotes']}")
    elif best["negation_differs"]:
        detail = ("the source's closest sentence is negated where the claim is not (or the "
                  "other way round) -- string matching cannot tell which is meant")
    else:
        detail = (f"the names and numbers appear together, but only {best['cover']:.0%} of what "
                  "the claim says about them does")
    return {"claim": claim, "status": UNVERIFIED, "detail": detail, "signals": sig}


def check_output(output_text: str, source_text: str) -> dict:
    """Every sentence in `output_text`, checked against `source_text`."""
    results = [check_claim(c, source_text) for c in split_claims(output_text)]
    counts = {GROUNDED: 0, CONTRADICTED: 0, UNVERIFIED: 0}
    for r in results:
        counts[r["status"]] += 1
    return {"claims": results, "counts": counts}
