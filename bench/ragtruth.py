"""Score sourced against RAGTruth (github.com/ParticleMedia/RAGTruth, MIT).

RAGTruth labels real model answers -- GPT-4, GPT-3.5, Llama-2, Mistral --
span by span for hallucinations, across summarization, QA and data-to-text.
A sentence counts as hallucinated when any labelled span overlaps it.

    curl -LO https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/dataset/response.jsonl
    curl -LO https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/dataset/source_info.jsonl
    python bench/ragtruth.py .            # the 2,700-answer test split

The number that matters most is the false-grounded rate: of the sentences
sourced calls `grounded`, how many were hallucinated. That is the error a
user acts on.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sourced.check import CONTRADICTED, GROUNDED, UNVERIFIED, check_claim  # noqa: E402
from sourced.claims import split_claims  # noqa: E402


def source_text(info) -> str:
    if isinstance(info, str):
        return info
    if isinstance(info, dict) and "passages" in info:
        return f"{info.get('question', '')}\n{info['passages']}"
    return json.dumps(info, ensure_ascii=False)  # data-to-text: structured records


def sentences(text: str):
    """(sentence, start, end) in the original response."""
    cursor = 0
    for claim in split_claims(text):
        start = text.find(claim, cursor)
        if start < 0:
            continue
        yield claim, start, start + len(claim)
        cursor = start + len(claim)


def main(folder: str, split: str = "test") -> None:
    folder = pathlib.Path(folder)
    sources = {}
    with open(folder / "source_info.jsonl", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            sources[row["source_id"]] = row
    # task -> verdict -> [hallucinated, clean]
    tally = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    with open(folder / "response.jsonl", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row["split"] != split:
                continue
            info = sources[row["source_id"]]
            text = source_text(info["source_info"])
            spans = [(l["start"], l["end"]) for l in row["labels"]]
            for claim, start, end in sentences(row["response"]):
                bad = any(s < end and e > start for s, e in spans)
                verdict = check_claim(claim, text)["status"]
                for task in (info["task_type"], "all"):
                    tally[task][verdict][0 if bad else 1] += 1

    print(f"RAGTruth {split} split, sentence level\n")
    print(f"{'task':10} {'sentences':>9} {'halluc.':>8} | {'grounded':>8} {'false-gr.':>9} | "
          f"{'contra.':>7} {'precision':>9} | {'unverified':>10} | {'caught':>6}")
    for task in ("Summary", "QA", "Data2txt", "all"):
        t = tally[task]
        total = sum(sum(v) for v in t.values())
        halluc = sum(v[0] for v in t.values())
        g_bad, g_ok = t[GROUNDED]
        c_bad, c_ok = t[CONTRADICTED]
        u = sum(t[UNVERIFIED])
        grounded = g_bad + g_ok
        print(f"{task:10} {total:>9} {halluc:>8} | {grounded:>8} {g_bad / max(grounded, 1):>9.1%} | "
              f"{c_bad + c_ok:>7} {c_bad / max(c_bad + c_ok, 1):>9.1%} | {u:>10} | "
              f"{(halluc - g_bad) / max(halluc, 1):>6.1%}")
    base = sum(tally["all"][v][0] for v in tally["all"]) / max(sum(sum(v) for v in tally["all"].values()), 1)
    print(f"\nbase rate: {base:.1%} of all sentences are hallucinated.")
    print("false-gr. = hallucinated share of `grounded`; caught = hallucinated sentences NOT called grounded.")


if __name__ == "__main__":
    main(*sys.argv[1:])
