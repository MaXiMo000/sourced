"""sourced check <output-file> <source-file> [source-file ...] [--json]"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from .check import check_output
from .judge import DEFAULT_MODEL, JudgeUnavailable, judge

_TAG = {"grounded": "OK", "contradicted": "XX", "unverified": "??"}


def _read(path: str) -> str:
    """A missing file, a directory given by mistake, or binary/undecodable
    content is a wrong argument, not a crash -- every sibling tool in this
    portfolio treats a bad file path as an actionable error message, not a
    traceback (found by testing this against an actual typo'd path, the
    same way providence's malformed-JSON crash was found)."""
    p = pathlib.Path(path)
    # Checked up front: on Windows, reading a directory raises
    # PermissionError, not IsADirectoryError, so the except below never
    # saw it and the user got a traceback.
    if p.is_dir():
        sys.exit(f"sourced: {path} is a directory, not a file")
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        sys.exit(f"sourced: no such file: {path}")
    except IsADirectoryError:
        sys.exit(f"sourced: {path} is a directory, not a file")
    except UnicodeDecodeError as exc:
        sys.exit(f"sourced: {path} is not valid UTF-8 text ({exc})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sourced")
    sub = parser.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser(
        "check", help="check each sentence of an LLM output against source text")
    check_p.add_argument("output_file", help="the LLM's output, one claim per sentence")
    check_p.add_argument("source_files", nargs="+", help="the context it should be grounded in")
    check_p.add_argument("--json", action="store_true", help="print the full report as JSON")
    check_p.add_argument("--judge", action="store_true",
                         help="ask Claude to decide the claims string matching left unverified "
                              "(needs: pip install 'sourced-evidence[judge]')")
    check_p.add_argument("--judge-model", default=DEFAULT_MODEL,
                         help=f"the model for --judge (default: {DEFAULT_MODEL})")

    batch_p = sub.add_parser(
        "batch", help="check many outputs: a JSONL file of {\"output\", \"sources\"} records")
    batch_p.add_argument("jsonl")
    batch_p.add_argument("--json", action="store_true", help="print one result per record, as JSONL")

    args = parser.parse_args(argv)
    if args.command == "batch":
        return _batch(args)

    output_text = _read(args.output_file)
    source_text = "\n".join(_read(f) for f in args.source_files)
    report = check_output(output_text, source_text)
    if args.judge:
        try:
            judge(report, source_text, model=args.judge_model)
        except JudgeUnavailable as exc:
            sys.exit(f"sourced: {exc}")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for r in report["claims"]:
            print(f"[{_TAG[r['status']]}] {r['claim']}")
            if r["status"] != "grounded":
                print(f"       {r['detail']}")
        c = report["counts"]
        print(f"\n{c['grounded']} grounded, {c['contradicted']} contradicted, "
              f"{c['unverified']} unverified")

    # Same convention as receipt/invariant: unverified is a legitimate "we
    # can't tell," not a failure -- only a contradiction (a claim actively
    # at odds with its own source) is a nonzero exit.
    return 1 if report["counts"]["contradicted"] > 0 else 0


def _batch(args) -> int:
    """Each line: {"id"?, "output": str, "sources": [str] | "source": str}.
    A malformed line is reported and counted, never skipped silently."""
    totals = {"grounded": 0, "contradicted": 0, "unverified": 0}
    records = bad = flagged = 0
    with open(args.jsonl, encoding="utf-8") as fh:
        for number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                sources = row.get("sources", row.get("source"))
                sources = [sources] if isinstance(sources, str) else list(sources)
                report = check_output(row["output"], "\n".join(sources))
            except (ValueError, KeyError, TypeError) as exc:
                bad += 1
                print(f"sourced: line {number} skipped: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            records += 1
            flagged += report["counts"]["contradicted"] > 0
            for k, v in report["counts"].items():
                totals[k] += v
            if args.json:
                print(json.dumps({"id": row.get("id", number), **report}))
    if not args.json:
        print(f"{records} record(s): {totals['grounded']} grounded, {totals['contradicted']} "
              f"contradicted, {totals['unverified']} unverified claims; {flagged} record(s) "
              f"with a contradiction" + (f"; {bad} malformed line(s)" if bad else ""))
    return 1 if flagged or bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
