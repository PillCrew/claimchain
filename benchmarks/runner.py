"""Run the deterministic benchmark and report extraction/verdict quality.

Usage::

    python -m benchmarks.runner          # human-readable table + summary
    python -m benchmarks.runner --json   # machine-readable JSON
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from claimchain.extract import Claim, extract_claims
from claimchain.verify import verify_claims

from .cases import CASES, KNOWN_LIMITATIONS, Case

MATCH_REL_TOL = 1e-6
MATCH_ABS_TOL = 1e-9


@dataclass
class CaseResult:
    case_id: str
    n_expected: int
    n_extracted: int
    matched: int = 0
    verdict_correct: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    results: List[CaseResult]
    precision: float
    recall: float
    f1: float
    verdict_accuracy: float
    case_pass_rate: float

    def as_dict(self) -> dict:
        return {
            "n_cases": len(self.results),
            "extraction_precision": round(self.precision, 4),
            "extraction_recall": round(self.recall, 4),
            "extraction_f1": round(self.f1, 4),
            "verdict_accuracy": round(self.verdict_accuracy, 4),
            "case_pass_rate": round(self.case_pass_rate, 4),
            "per_case": [
                {
                    "id": r.case_id,
                    "expected": r.n_expected,
                    "extracted": r.n_extracted,
                    "matched": r.matched,
                    "verdict_correct": r.verdict_correct,
                    "errors": r.errors,
                }
                for r in self.results
            ],
        }


def _value_close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=MATCH_REL_TOL, abs_tol=MATCH_ABS_TOL)


def _match(
    expected: List[Tuple[str, float]],
    extracted: List[Tuple[str, float]],
) -> Tuple[int, List[str]]:
    """Greedily pair expected claims with extracted claims of the same metric.

    Returns the number of matched pairs and a list of human-readable mismatch
    descriptions (missing expected metrics and unexpected extracted metrics).
    """

    used: List[bool] = [False] * len(extracted)
    matched = 0
    errors: List[str] = []

    for metric, value in expected:
        best: Optional[int] = None
        best_dist = float("inf")
        for i, (emetric, evalue) in enumerate(extracted):
            if used[i] or emetric != metric:
                continue
            dist = abs(evalue - value)
            if dist < best_dist and _value_close(evalue, value):
                best, best_dist = i, dist
        if best is None:
            errors.append(f"missing expected {metric}={value:g}")
        else:
            used[best] = True
            matched += 1

    for i, (emetric, evalue) in enumerate(extracted):
        if not used[i]:
            errors.append(f"unexpected extracted {emetric}={evalue:g}")

    return matched, errors


def _run_case(case: Case) -> CaseResult:
    claims: List[Claim] = extract_claims(case.text, default_token=case.symbol or None)
    verdicts = verify_claims(claims, case.truth)

    extracted_vals: List[Tuple[str, float]] = [(c.metric, c.value) for c in claims]
    expected_vals: List[Tuple[str, float]] = [(e.metric, e.value) for e in case.expected]

    matched, errors = _match(expected_vals, extracted_vals)

    verdict_by_claim = {(c.metric, c.value): v.verdict for c, v in zip(claims, verdicts.verdicts)}
    verdict_correct = 0
    for exp in case.expected:
        # find the matched extracted claim for this expected claim
        for c in claims:
            if c.metric == exp.metric and _value_close(c.value, exp.value):
                if verdict_by_claim[(c.metric, c.value)] == exp.verdict:
                    verdict_correct += 1
                break

    return CaseResult(
        case_id=case.id,
        n_expected=len(case.expected),
        n_extracted=len(claims),
        matched=matched,
        verdict_correct=verdict_correct,
        errors=errors,
    )


def run_benchmark(cases: Optional[List[Case]] = None) -> BenchmarkResult:
    cases = cases if cases is not None else CASES
    results = [_run_case(c) for c in cases]

    tp = sum(r.matched for r in results)
    fp = sum(r.n_extracted - r.matched for r in results)
    fn = sum(r.n_expected - r.matched for r in results)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    verdict_accuracy = tp and sum(r.verdict_correct for r in results) / tp or 1.0
    case_pass_rate = sum(1 for r in results if not r.errors) / len(results) if results else 1.0

    return BenchmarkResult(
        results=results,
        precision=precision,
        recall=recall,
        f1=f1,
        verdict_accuracy=verdict_accuracy,
        case_pass_rate=case_pass_rate,
    )


def _render_table(result: BenchmarkResult) -> str:
    lines = [f"{'CASE':<28} {'EXP':>3} {'GOT':>3} {'MATCH':>5} {'VERDICT':>7}"]
    lines.append("-" * 56)
    for r in result.results:
        verdict = f"{r.verdict_correct}/{r.matched}" if r.matched else "-"
        lines.append(f"{r.case_id:<28} {r.n_expected:>3} {r.n_extracted:>3} {r.matched:>5} {verdict:>7}")
    lines.append("-" * 56)
    return "\n".join(lines)


def _render_summary(result: BenchmarkResult) -> str:
    return "\n".join([
        f"cases:              {len(result.results)}",
        f"extraction precision {result.precision:.3f}",
        f"extraction recall    {result.recall:.3f}",
        f"extraction F1        {result.f1:.3f}",
        f"verdict accuracy     {result.verdict_accuracy:.3f}",
        f"case pass rate       {result.case_pass_rate:.3f}",
    ])


def _render_errors(result: BenchmarkResult) -> str:
    lines = []
    for r in result.results:
        if r.errors:
            lines.append(f"\n{r.case_id}:")
            for e in r.errors:
                lines.append(f"  - {e}")
    return "\n".join(lines)


def _render_limitations() -> str:
    lines = ["\nKnown limitations (not scored):"]
    for lim in KNOWN_LIMITATIONS:
        claims = extract_claims(lim.text, default_token=lim.symbol or None)
        verdicts = verify_claims(claims, lim.truth)
        observed = "; ".join(f"{c.metric}={c.value:g}->{v.verdict}" for c, v in zip(claims, verdicts.verdicts))
        lines.append(f"  {lim.id}: {lim.note}")
        lines.append(f"    observed: {observed or '(nothing extracted)'}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    result = run_benchmark()

    if "--json" in argv:
        print(json.dumps(result.as_dict(), indent=2))
        return 0

    print(_render_table(result))
    print()
    print(_render_summary(result))
    errors = _render_errors(result)
    if errors:
        print(errors)
    print(_render_limitations())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
