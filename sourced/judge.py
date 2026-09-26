"""Optional second pass: Claude adjudicates the claims the string-matching
pass couldn't decide.

The deterministic pass only sees numbers, quotes and names, so paraphrase
("fifty-six billion dollars" vs "$56 billion"), a changed verb ("fell" vs
"rose"), or a claim with no concrete tokens all come back `unverified`.
This sends exactly those claims -- never the ones already decided -- to
Claude with the source, and gets back grounded / contradicted / unverified
per claim.

The judge is held to the same bar as everything else here: every
grounded or contradicted verdict must quote its evidence verbatim from the
source, and that quote is checked against the source text. A verdict whose
quote isn't actually there is discarded and the claim stays unverified --
the model can't talk a claim into "grounded".

Needs `pip install sourced-evidence[judge]` (the anthropic SDK) and
credentials the SDK can find (ANTHROPIC_API_KEY, or `ant auth login`).
"""
from __future__ import annotations

import json

from .check import CONTRADICTED, GROUNDED, UNVERIFIED

DEFAULT_MODEL = "claude-opus-5"

SYSTEM = """You check whether claims made by an AI system are supported by a source document.

For each numbered claim, decide:
- "grounded": the source states the claim's facts, possibly in different words.
- "contradicted": the source states something incompatible with the claim.
- "unverified": the source neither supports nor contradicts it. Use this whenever you are unsure.

Judge only against the source below, never against your own knowledge. For every grounded or \
contradicted verdict, "evidence" must be an exact, verbatim quote copied from the source (a sentence \
or phrase, not paraphrased). For unverified, "evidence" is an empty string.

<source>
{source}
</source>"""

SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "integer"},
                    "status": {"type": "string", "enum": [GROUNDED, CONTRADICTED, UNVERIFIED]},
                    "evidence": {"type": "string"},
                },
                "required": ["claim", "status", "evidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}


class JudgeUnavailable(RuntimeError):
    """The judge couldn't run at all -- a clear message for the CLI, not a crash."""


def _normalize(text: str) -> str:
    return " ".join(text.replace("’", "'").replace("“", '"').replace("”", '"').split())


def _make_client():
    try:
        import anthropic
    except ModuleNotFoundError:
        raise JudgeUnavailable("--judge needs the anthropic SDK: pip install 'sourced-evidence[judge]'") from None
    return anthropic.Anthropic()


def judge(report: dict, source: str, *, model: str = DEFAULT_MODEL, client=None) -> dict:
    """Updates `report` (from check_output) in place: each `unverified`
    claim the judge can decide gets its verdict plus a `judge` record.
    Returns the report."""
    pending = [(i, r) for i, r in enumerate(report["claims"]) if r["status"] == UNVERIFIED]
    report["judge"] = {"model": model, "asked": len(pending), "decided": 0, "discarded": 0}
    if not pending:
        return report

    client = client or _make_client()
    numbered = "\n".join(f"{n}. {r['claim']}" for n, (_, r) in enumerate(pending, 1))
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            # A policy decline is re-run server-side on Anthropic's
            # recommended fallback model instead of failing the check.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            # The source is the long, stable part: cached, so re-checking
            # the same source (the usual CI loop) reads it at cache prices.
            system=[{"type": "text", "text": SYSTEM.format(source=source),
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"Claims:\n{numbered}"}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        )
    except Exception as exc:  # noqa: BLE001 -- the SDK's typed errors, reported plainly
        raise JudgeUnavailable(f"the judge request failed: {type(exc).__name__}: {exc}") from exc

    if response.stop_reason == "refusal":
        report["judge"]["refused"] = True
        return report
    if response.stop_reason == "max_tokens":
        raise JudgeUnavailable("the judge's answer was cut off (max_tokens); try fewer claims per run")

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        verdicts = json.loads(text)["verdicts"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise JudgeUnavailable(f"the judge returned an unreadable answer ({exc})") from exc

    haystack = _normalize(source)
    for v in verdicts:
        n = v.get("claim")
        if not isinstance(n, int) or not 1 <= n <= len(pending) or v.get("status") not in (GROUNDED, CONTRADICTED):
            continue
        _, result = pending[n - 1]
        evidence = (v.get("evidence") or "").strip()
        if not evidence or _normalize(evidence) not in haystack:
            # Not a real quote from the source: don't trust the verdict.
            report["judge"]["discarded"] += 1
            continue
        result["status"] = v["status"]
        result["detail"] = f"judged {v['status']} by {model}: the source says \"{evidence}\""
        result["judge"] = {"model": model, "evidence": evidence}
        report["judge"]["decided"] += 1

    report["counts"] = {s: sum(1 for r in report["claims"] if r["status"] == s)
                        for s in (GROUNDED, CONTRADICTED, UNVERIFIED)}
    return report
