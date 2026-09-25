# sourced

[![ci](https://github.com/MaXiMo000/sourced/actions/workflows/ci.yml/badge.svg)](https://github.com/MaXiMo000/sourced/actions/workflows/ci.yml)

**Checks an LLM's output against its own source context, claim by claim --
`grounded`, `contradicted`, or `unverified`, never one blended trust score.**

A RAG pipeline retrieves the right documents and still generates a sentence
those documents don't support -- a wrong number, an entity the source never
mentions, a stat close enough to sound plausible. Most RAG evaluation
scores *retrieval quality*: did the right chunks come back. Almost nothing
checks the *output* sentence by sentence against what was actually
retrieved. `sourced` does that second, narrower thing.

```
$ sourced check output.txt source.txt
[OK] Microsoft reported revenue of $56 billion.
[XX] Microsoft grew 40% year over year.
       claims 40% near 'Microsoft', but the source's own text near that
       entity says ['56 billion', '8%']
[??] The outlook remains uncertain.
       no checkable numbers, quoted text, or capitalized entities in this claim

1 grounded, 1 contradicted, 1 unverified
```

(That transcript is real output, not illustrative -- `source.txt` says growth
was 8%; note the second claim repeats "Microsoft" by name rather than
saying "it," because pronoun coreference isn't resolved -- see "What this
does NOT do.")

## Install

```
pip install sourced-evidence   # the command it installs is `sourced`
```

(`sourced` was already taken on PyPI -- same story as `receipt-evidence`,
`providence-evidence`, and `custody-evidence` in this portfolio.)

## Use

```
sourced check <output-file> <source-file> [source-file ...] [--json]
```

`output-file` is the LLM's generated text. `source-file`(s) are the
context it was supposed to be grounded in -- the retrieved chunks, the
document it summarized, the transcript it's answering questions about.
Multiple source files are concatenated before checking.

Exit code is `1` only if any claim is `contradicted` -- same convention as
[`receipt`](https://github.com/MaXiMo000/receipt) and
[`invariant`](https://github.com/MaXiMo000/invariant): `unverified` is a
legitimate "can't tell," not a failure.

## How a claim gets checked

1. **Split into claims.** Every sentence in the output is one claim
   candidate -- no attempt to tell a factual assertion from an opinion or
   a hedge (`sourced/claims.py`).
2. **Extract signals.** Numbers, quoted substrings, and capitalized
   entity-shaped phrases (`sourced/signals.py`) -- the concrete, matchable
   facts a source text either does or doesn't contain. Numbers are compared
   by value, not as text: `1,000` = `1000`, `$56 billion` = `56B` = `56bn`,
   `8%` = `8 percent`, and `5` is never "found" inside a source's `56`.
3. **Classify against the source** (`sourced/check.py`):
   - **`grounded`** -- every number, quote, and entity in the claim appears
     in the source.
   - **`contradicted`** -- a claim's number doesn't appear in the source at
     all, but an entity from the *same claim* does, near a *different*
     number. Narrow on purpose: this only fires when there's a real shared
     anchor pinning the comparison to the same subject, never "two
     different numbers exist somewhere in a long document."
   - **`unverified`** -- everything else: no checkable signals in the claim
     at all, or some signal simply isn't found anywhere in the source.

## What this does NOT do

This is the part worth reading before trusting a result.

- **No semantic understanding, no paraphrase matching.** "Revenue was $56
  billion" and "the company made fifty-six billion dollars" are the same
  fact and this will not see it that way -- it matches strings and
  numbers, not meaning. A real semantic entailment checker needs a
  language model; that's real future work (an optional LLM-backed
  adjudication pass, the same shape `invariant`'s cascade or LabLedger's
  Gemini stage already use elsewhere in this portfolio -- degrade
  gracefully without it, don't require it), not built here.
- **No real named-entity recognition.** `signals.proper_nouns()` is a
  capitalization heuristic, not a trained model. "Bank of America" splits
  into `Bank` and `America` because a lowercase joiner breaks the
  capitalized-word chain. Documented in `signals.py`, not hidden.
- **No real sentence tokenizer.** `claims.split_claims()` is a regex.
  "Dr. Smith signed the report." reads as two sentences. Ordinary prose
  splits correctly; abbreviation-heavy text won't always.
- **No pronoun or coreference resolution.** "Microsoft reported $56B. It
  grew 40%." -- the second sentence's "It" is correctly excluded as an
  entity (it's a pronoun, not a name), so there's no anchor to check that
  claim's number against, and it comes back `unverified` rather than
  `contradicted`. Each claim is checked entirely on its own; a real fix
  needs coreference resolution, real NLP work of its own, not attempted
  here.
- **Contradiction detection is deliberately conservative**, and that cuts
  both ways: a real contradiction with no shared entity to anchor on comes
  back `unverified`, not `contradicted` -- this will under-report
  contradictions before it will over-report them. That's the intended
  trade for a tool whose whole point is not manufacturing false
  accusations against a source.

## Tests

```
pip install -e .
python tests/test_claims.py     # sentence splitting
python tests/test_signals.py    # number/quote/entity extraction
python tests/test_check.py      # the grounded/contradicted/unverified decision
python tests/test_cli.py        # the real CLI entry point, real files, real argv
```

41 tests. Several exist specifically because a first pass got something
wrong and testing against ordinary prose (not synthetic numbers-only
input) caught it -- e.g. a number regex that swallowed a following
sentence period (`"42."` parsed as the number `42.`), a sentence-
initial entity ("Microsoft" opening a sentence) needing case-insensitive
matching against a source that uses the same word lowercase mid-sentence,
without that leniency being used for anything else, and (found live
during a later audit) American-style closing punctuation putting the
period *inside* a quote (`"four hours."` not `"four hours".`) silently
merging two sentences into one claim -- the sentence-end regex only ever
checked for `[.!?]` immediately before the split point, never a quote
mark sitting in front of it.

MIT licensed.
