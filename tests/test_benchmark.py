"""Regression gate: the benchmark must stay fully green.

The whole point of the benchmark is to keep extraction honest as the engine
evolves. If these thresholds regress, a change silently broke a documented
claim pattern and must be fixed before release.
"""

from benchmarks.runner import run_benchmark


def test_benchmark_extraction_is_full_score():
    result = run_benchmark()
    assert result.f1 >= 0.999, f"extraction F1 regressed: {result.f1:.4f}"
    assert result.verdict_accuracy >= 0.999, (
        f"verdict accuracy regressed: {result.verdict_accuracy:.4f}"
    )


def test_benchmark_every_case_passes():
    result = run_benchmark()
    failing = [r.case_id for r in result.results if r.errors]
    assert not failing, f"benchmark cases with errors: {failing}"
