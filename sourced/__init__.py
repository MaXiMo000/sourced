"""sourced: check an LLM's output against its own sources, claim by claim.

    from sourced import check, assert_grounded

    report = check(answer, [doc1, doc2])          # {"claims": [...], "counts": {...}}
    assert_grounded(answer, [doc1, doc2])         # in a test or an eval pipeline
"""
from __future__ import annotations

__version__ = "0.4.0"

# Loaded before `check` below is defined: importing the `sourced.check`
# submodule later would rebind the package's `check` to the module.
from . import check as _check_module  # noqa: E402


def check(output: str, sources) -> dict:
    """Every sentence of `output` checked against `sources` (a string, or a
    list of them): grounded, contradicted or unverified."""
    text = sources if isinstance(sources, str) else "\n\n".join(sources)
    return _check_module.check_output(output, text)


def assert_grounded(output: str, sources, *, allow_unverified: bool = True) -> dict:
    """Raise AssertionError naming every contradicted claim -- and, with
    `allow_unverified=False`, every claim the sources could not confirm.
    Returns the report when it passes, so a test can look further."""
    report = check(output, sources)
    failing = ({_check_module.CONTRADICTED} if allow_unverified
               else {_check_module.CONTRADICTED, _check_module.UNVERIFIED})
    bad = [c for c in report["claims"] if c["status"] in failing]
    if bad:
        lines = "\n".join(f"  [{c['status']}] {c['claim']}\n      {c['detail']}" for c in bad)
        raise AssertionError(f"{len(bad)} claim(s) not grounded in the sources:\n{lines}")
    return report
