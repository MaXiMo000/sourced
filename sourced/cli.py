"""sourced check <output-file> <source-file> [source-file ...] [--json]"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from .check import check_output

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

    args = parser.parse_args(argv)

    output_text = _read(args.output_file)
    source_text = "\n".join(_read(f) for f in args.source_files)
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
