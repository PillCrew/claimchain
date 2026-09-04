"""Human- and machine-readable rendering of a verification result."""

from __future__ import annotations

import json
from typing import Optional

from .extract import Claim
from .verify import VerdictSet, VERIFIED, CONTRADICTED, UNRESOLVED

# ASCII-safe markers so the table renders identically on any terminal/console.
ICONS = {
    VERIFIED: "OK ",
    CONTRADICTED: "NO ",
    UNRESOLVED: "? ",
}


def _fmt(value: Optional[float], metric: str) -> str:
    if value is None:
        return "n/a"
    if metric.startswith("change_"):
        return f"{value:+.2f}%"
    if metric in ("volume_liquidity_ratio",):
        return f"{value:.2f}x"
    if metric == "age_days":
        return f"{value:.1f}d"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.2f}K"
    if metric in ("market_cap", "volume", "liquidity", "price", "fdv"):
        return f"${value:.6f}".rstrip("0").rstrip(".")
    return f"{value:.6f}"


def _head(label: str) -> str:
    # 23 wide: the longest metric ("volume_liquidity_ratio") is 22 chars, so
    # this always leaves at least one space between columns.
    return f"{label:<23}"


def render_table(set_: VerdictSet) -> str:
    """Render a clean monospace table of claim -> verdict."""

    lines: list[str] = []
    lines.append(f"TOKEN: {set_.token.symbol if set_.token else 'UNKNOWN'}")
    lines.append("-" * 78)
    lines.append(f"{_head('METRIC')}{_head('CLAIM')}{_head('ACTUAL')}VERDICT")
    lines.append("-" * 78)
    for v in set_.verdicts:
        icon = ICONS[v.verdict]
        metric = v.claim.metric
        lines.append(
            f"{_head(metric)}{_head(_fmt(v.claim.value, metric))}"
            f"{_head(_fmt(v.actual, metric))}{icon} {v.verdict}"
        )
    lines.append("-" * 78)
    counts = set_.counts
    lines.append(
        f"GROUNDEDNESS SCORE: {set_.score}/100 "
        f"(OK {counts[VERIFIED]} | NO {counts[CONTRADICTED]} | ? {counts[UNRESOLVED]})"
    )
    return "\n".join(lines)


def render_json(set_: VerdictSet) -> str:
    payload = {
        "token": {
            "address": set_.token.address,
            "symbol": set_.token.symbol,
            "name": set_.token.name,
            "price_usd": set_.token.price_usd,
            "market_cap": set_.token.market_cap,
            "liquidity_usd": set_.token.liquidity_usd,
            "volume_usd": set_.token.volume_usd,
            "age_days": set_.token.age_days,
        } if set_.token else None,
        "score": set_.score,
        "counts": set_.counts,
        "claims": [
            {
                "metric": v.claim.metric,
                "claimed": v.claim.value,
                "actual": v.actual,
                "verdict": v.verdict,
                "raw": v.claim.raw,
                "note": v.note,
            }
            for v in set_.verdicts
        ],
    }
    return json.dumps(payload, indent=2)


def render(set_: VerdictSet, fmt: str = "table") -> str:
    if fmt == "json":
        return render_json(set_)
    return render_table(set_)
