"""Check one claim against source text: grounded, contradicted, or
unverified -- never a blended trust score. See README for exactly what
each status means, and what this deliberately does not attempt (semantic
entailment, paraphrase matching -- see "What this doesn't do").
"""
from __future__ import annotations

from . import signals
from .claims import split_claims

GROUNDED, CONTRADICTED, UNVERIFIED = "grounded", "contradicted", "unverified"


def _window(text: str, index: int, radius: int = 60) -> str:
    return text[max(0, index - radius): index + radius]


def check_claim(claim: str, source: str) -> dict:
    nums = signals.numbers(claim)
    ents = signals.proper_nouns(claim)
    quoted = signals.quotes(claim)

    if not nums and not ents and not quoted:
        return {
            "claim": claim, "status": UNVERIFIED,
            "detail": "no checkable numbers, quoted text, or capitalized entities in this claim",
            "signals": {"numbers": [], "entities": [], "quotes": []},
        }

    # Contradiction: a number in the claim doesn't appear anywhere in the
    # source, but an entity from the same claim does, near a *different*
    # number. Narrow and conservative on purpose -- this only fires when
    # there's a real anchor (a shared entity) pinning the comparison to the
    # same subject, not "any two different numbers exist somewhere in a
    # long document," which would be a false-contradiction machine.
    contradictions = []
    for ent in ents:
        idx = source.find(ent)
        if idx == -1:
            continue
        nearby_nums = signals.numbers(_window(source, idx))
        for n in nums:
            if n not in source and nearby_nums and n not in nearby_nums:
                contradictions.append({
                    "claim_number": n, "entity": ent,
                    "source_numbers_nearby": nearby_nums,
                })

    if contradictions:
        first = contradictions[0]
        return {
            "claim": claim, "status": CONTRADICTED,
            "detail": (f"claims {first['claim_number']} near '{first['entity']}', but "
                       f"the source's own text near that entity says "
                       f"{first['source_numbers_nearby']}"),
            "signals": {"numbers": nums, "entities": ents, "quotes": quoted},
            "contradictions": contradictions,
        }

    missing_numbers = [n for n in nums if n not in source]
    # Case-insensitive here, unlike the contradiction anchor above: a
    # sentence-initial entity like "Revenue" is only capitalized because of
    # its position, and the same word appears lowercase mid-sentence in
    # most real source text ("Q3 revenue was..."). Exact-case matching
    # would report a real match as "missing" for no reason other than
    # capitalization -- a worse failure for a grounding check than being
    # slightly lenient. Contradiction anchoring stays case-sensitive
    # (source.find(ent) above) precisely because it needs to be stricter.
    source_lower = source.lower()
    missing_entities = [e for e in ents if e.lower() not in source_lower]
    missing_quotes = [q for q in quoted if q not in source]
    total = len(nums) + len(ents) + len(quoted)
    missing = len(missing_numbers) + len(missing_entities) + len(missing_quotes)

    if missing == 0:
        return {
            "claim": claim, "status": GROUNDED,
            "detail": "every number, entity, and quoted phrase in this claim appears in the source",
            "signals": {"numbers": nums, "entities": ents, "quotes": quoted},
        }
    return {
        "claim": claim, "status": UNVERIFIED,
        "detail": (f"{missing}/{total} signal(s) not found in the source -- "
                   f"numbers {missing_numbers}, entities {missing_entities}, "
                   f"quotes {missing_quotes}"),
        "signals": {"numbers": nums, "entities": ents, "quotes": quoted},
    }


def check_output(output_text: str, source_text: str) -> dict:
    """Every sentence in `output_text`, checked against `source_text`."""
    results = [check_claim(c, source_text) for c in split_claims(output_text)]
    counts = {GROUNDED: 0, CONTRADICTED: 0, UNVERIFIED: 0}
    for r in results:
        counts[r["status"]] += 1
    return {"claims": results, "counts": counts}
