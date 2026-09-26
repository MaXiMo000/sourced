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
   - **`grounded`** -- every number, quote and name in the claim appears
     **in one passage** of the source (three consecutive sentences),
     together with at least 60% of the claim's own content words, and the
     source's closest sentence is not negated where the claim isn't (or
     the other way round). At least one signal must be a real anchor: a
     claim whose only match is its capitalized first word ("Operating
     costs rose...") stays `unverified`.
   - **`contradicted`** -- a passage about the same thing (every name in
     the claim, most of its words) states a different number, and not the
     claim's. The report shows the numbers that passage gives near those
     names.
   - **`unverified`** -- everything else, with the reason: which signals
     never appear together, a negation mismatch, or names that co-occur
     while most of what the claim says about them doesn't.

**Why local.** The first version grounded a claim when each signal
appeared *anywhere* in the source. Checked against the 73 KB Wikipedia
article on PostgreSQL, it called three false sentences grounded:

```
Stonebraker returned to Berkeley in 1991 ...   (the source: 1985; 1991 is elsewhere)
POSTGRES reused most of the Ingres code.        (the source: "but not its code")
Berkeley released POSTGRES under a GPL license. (the source: an MIT License variant)
```

Now: the first is `contradicted` (the passage says 1982 and 1985), the
other two `unverified`, and the three true sentences in the same summary
stay `grounded`.

## `--judge`: let Claude decide what string matching can't

```
pip install 'sourced-evidence[judge]'
sourced check output.txt source.txt --judge
```

String matching can't see paraphrase ("costs went down a lot" vs
"operating costs fell sharply") or a flipped verb, so those claims come
back `unverified`. `--judge` sends **only those claims** -- never ones
already decided -- to Claude (`claude-opus-5` by default, `--judge-model`
to change it) with the source, and applies its grounded / contradicted
verdicts.

The judge is held to the same standard as the rest of the tool: every
verdict must quote its evidence **verbatim from the source**, and sourced
checks that quote is really there. A verdict backed by a quote that isn't
in the source is discarded and the claim stays `unverified` -- the model
can't talk a claim into `grounded`. Its reasons show up in the report:

```
[OK] Costs went down a lot after the reorganization.
[XX] Operating costs rose after the restructuring.
       judged contradicted by claude-opus-5: the source says "Operating costs fell sharply"
```

(Shape of the output, not a recorded run.) One request per check: the
source goes in a cached system prompt, so re-checking against the same
source -- the usual CI loop -- reads it at cache prices. A safety refusal
is re-run server-side on Anthropic's recommended fallback model
(`fallbacks: "default"`); if the chain still refuses, the claims stay
`unverified` and the report says so. Credentials are whatever the
anthropic SDK finds (`ANTHROPIC_API_KEY`, or `ant auth login`). Without
`--judge`, sourced never makes a network call.

## What this does NOT do

This is the part worth reading before trusting a result.

- **No semantic understanding, without `--judge`.** "Revenue was $56
  billion" and "the company made fifty-six billion dollars" are the same
  fact, and the string pass will not see it that way -- it matches strings
  and numbers, not meaning. `--judge` (above) is the optional
  meaning-level pass; nothing requires it.
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
python tests/test_judge.py      # --judge, against a stand-in client (no network)
```

Several tests exist specifically because a first pass got something
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
