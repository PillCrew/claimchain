"""Adjudicate whether an agent's claims match the on-chain ground truth.

Each claim is compared against a :class:`~claimchain.providers.TokenTruth` and
issued one of three verdicts:

* ``VERIFIED``    - the claim is within the tolerance window of reality.
* ``CONTRADICTED`` - the claim is materially wrong (hallucination / stale data).
* ``UNRESOLVED``  - we could not get ground truth, or the metric is out of scope.

A value-neutral "groundedness score" (0-100) summarizes how much of the agent's
analysis is actually true, so downstream systems (and the X community) can see
whether a verdict is grounded without reading the whole table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .extract import Claim
from .providers import TokenTruth

VERIFIED = "VERIFIED"
CONTRADICTED = "CONTRADICTED"
UNRESOLVED = "UNRESOLVED"

# Defaults. Percent metrics use a flat tolerance in percentage points; currency
# and scalar metrics use a relative (fraction) tolerance.
DEFAULTS = {
    "percent_pp": 2.0,   # +/-2 percentage points on change_* claims
    "relative": 0.20,    # +/-20% on dollar/scalar claims unless overridden
}


@dataclass
class Verdict:
    claim: Claim
    verdict: str
    actual: Optional[float] = None
    diff_percent: Optional[float] = None
    note: str = ""


@dataclass
class VerdictSet:
    token: Optional[TokenTruth]
    verdicts: List[Verdict] = field(default_factory=list)

    @property
    def score(self) -> int:
        if not self.verdicts:
            return 100
        total = sum(1 for v in self.verdicts if v.verdict == VERIFIED)
        return round(100 * total / len(self.verdicts))

    @property
    def counts(self) -> dict:
        out = {VERIFIED: 0, CONTRADICTED: 0, UNRESOLVED: 0}
        for v in self.verdicts:
            out[v.verdict] += 1
        return out


# Maps a claim metric to the attribute on TokenTruth that holds its ground truth.
_METRIC_ATTR = {
    "change_5m": "change_5m",
    "change_1h": "change_1h",
    "change_6h": "change_6h",
    "change_24h": "change_24h",
    "market_cap": "market_cap",
    "fdv": "fdv",
    "liquidity": "liquidity_usd",
    "volume": "volume_usd",
    "price": "price_usd",
}


def resolve_actual(truth: TokenTruth, metric: str) -> Optional[float]:
    """Resolve a claim metric to its comparable ground-truth value.

    Some metrics are computed properties (``age_days``, ``volume_liquidity_ratio``)
    rather than stored attributes, and attribute names differ from claim names
    (``volume`` -> ``volume_usd``).
    """

    if metric == "age_days":
        return truth.age_days
    if metric == "volume_liquidity_ratio":
        return truth.volume_liquidity_ratio
    return getattr(truth, _METRIC_ATTR.get(metric, metric), None)


def verify_claim(claim: Claim, truth: Optional[TokenTruth], percent_pp: float = DEFAULTS["percent_pp"],
                 relative: float = DEFAULTS["relative"]) -> Verdict:
    """Compare one ``claim`` against ``truth`` and produce a :class:`Verdict`."""

    if truth is None:
        return Verdict(claim=claim, verdict=UNRESOLVED, note="no ground truth available")

    actual = resolve_actual(truth, claim.metric)

    if actual is None:
        return Verdict(claim=claim, verdict=UNRESOLVED, note=f"{claim.metric} not provided by source")

    expected = claim.value
    if claim.metric.startswith("change_"):
        # Percent change: compare in percentage points.
        diff = expected - actual
        within = abs(diff) <= percent_pp
    else:
        # Currency/scalar: relative tolerance.
        if actual == 0:
            within = abs(expected) < 1e-9
        else:
            rel = abs(expected - actual) / abs(actual)
            within = rel <= relative

    diff_percent = None
    if claim.metric.startswith("change_"):
        diff_percent = expected - actual
    elif actual:
        diff_percent = ((expected - actual) / abs(actual)) * 100.0

    if within:
        verdict = VERIFIED
        note = f"within tolerance (actual {actual:g})"
    else:
        verdict = CONTRADICTED
        note = f"claim {expected:g} vs actual {actual:g}"

    return Verdict(claim=claim, verdict=verdict, actual=actual, diff_percent=diff_percent, note=note)


def verify_claims(claims: List[Claim], truth: Optional[TokenTruth],
                  percent_pp: float = DEFAULTS["percent_pp"],
                  relative: float = DEFAULTS["relative"]) -> VerdictSet:
    return VerdictSet(
        token=truth,
        verdicts=[verify_claim(c, truth, percent_pp, relative) for c in claims],
    )
