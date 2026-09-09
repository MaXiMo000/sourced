"""sourced check <output-file> <source-file> [source-file ...] [--json]"""
from __future__ import annotations

import argparse
import json
import pathlib

from .check import check_output

_TAG = {"grounded": "OK", "contradicted": "XX", "unverified": "??"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sourced")
    sub = parser.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser(
        "check", help="check each sentence of an LLM output against source text")
    check_p.add_argument("output_file", help="the LLM's output, one claim per sentence")
    check_p.add_argument("source_files", nargs="+", help="the context it should be grounded in")
    check_p.add_argument("--json", action="store_true", help="print the full report as JSON")

    args = parser.parse_args(argv)

    output_text = pathlib.Path(args.output_file).read_text(encoding="utf-8")
    source_text = "\n".join(
        pathlib.Path(f).read_text(encoding="utf-8") for f in args.source_files)
    report = check_output(output_text, source_text)

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


if __name__ == "__main__":
    raise SystemExit(main())
