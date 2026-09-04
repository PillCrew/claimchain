"""Labeled benchmark cases.

Each :class:`Case` is fully deterministic: the agent's prose is paired with a
pinned ground-truth snapshot and the exact claims (metric, value, verdict) a
correct implementation should produce.

A second list, :data:`KNOWN_LIMITATIONS`, documents inputs the current engine
deliberately does *not* handle (e.g. negation). The runner reports these
separately so the README can be honest about the boundaries of the tool.
"""

from __future__ import annotations

from dataclasses import dataclass

from claimchain.providers import TokenTruth

VERIFIED = "VERIFIED"
CONTRADICTED = "CONTRADICTED"


@dataclass(frozen=True)
class ExpectedClaim:
    metric: str
    value: float
    verdict: str


@dataclass(frozen=True)
class Case:
    id: str
    text: str
    symbol: str
    truth: TokenTruth
    expected: tuple[ExpectedClaim, ...]


@dataclass(frozen=True)
class KnownLimitation:
    id: str
    text: str
    symbol: str
    truth: TokenTruth
    note: str


CASES: list[Case] = [
    # ── happy path: everything matches reality ──────────────────────────────
    Case(
        id="happy_all_verified",
        symbol="BONK",
        text=(
            "BONK +3.1% 1h · +5.2% 24h · $608.6K mcap · $269.3K volume · "
            "$80.4K liquidity · 19.5d old · entry $0.0006 · 3.3x vol/liq"
        ),
        truth=TokenTruth(
            address="a1", symbol="BONK", price_usd=0.0006,
            change_1h=3.1, change_24h=5.2,
            volume_usd=269_300, liquidity_usd=80_400, market_cap=608_600,
            age_seconds=19.5 * 86400,
        ),
        expected=(
            ExpectedClaim("change_1h", 3.1, VERIFIED),
            ExpectedClaim("change_24h", 5.2, VERIFIED),
            ExpectedClaim("market_cap", 608_600, VERIFIED),
            ExpectedClaim("volume", 269_300, VERIFIED),
            ExpectedClaim("liquidity", 80_400, VERIFIED),
            ExpectedClaim("age_days", 19.5, VERIFIED),
            ExpectedClaim("price", 0.0006, VERIFIED),
            ExpectedClaim("volume_liquidity_ratio", 3.3, VERIFIED),
        ),
    ),

    # ── the classic hallucinating crew: every number is wrong ──────────────
    Case(
        id="happy_all_contradicted",
        symbol="BONK",
        text=(
            "BONK $1.5B market cap · $170M volume · $1.2M liquidity · "
            "price $0.00005 · 1347d old · 141x vol/liq"
        ),
        truth=TokenTruth(
            address="a1", symbol="BONK", price_usd=0.000002907,
            volume_usd=127_670, liquidity_usd=199_370, market_cap=255_670_000,
            age_seconds=1347.4 * 86400,
        ),
        expected=(
            ExpectedClaim("market_cap", 1_500_000_000, CONTRADICTED),
            ExpectedClaim("volume", 170_000_000, CONTRADICTED),
            ExpectedClaim("liquidity", 1_200_000, CONTRADICTED),
            ExpectedClaim("price", 0.00005, CONTRADICTED),
            ExpectedClaim("age_days", 1347.0, VERIFIED),  # 1347d ≈ 1347.4d
            ExpectedClaim("volume_liquidity_ratio", 141.0, CONTRADICTED),
        ),
    ),

    # ── bare sub-$1 price has no unit suffix ───────────────────────────────
    Case(
        id="price_bare_small",
        symbol="BONK",
        text="BONK is currently $0.0000029",
        truth=TokenTruth(address="a1", symbol="BONK", price_usd=0.0000029),
        expected=(ExpectedClaim("price", 0.0000029, VERIFIED),),
    ),

    # ── leading price hints: entry / stop / target ─────────────────────────
    Case(
        id="price_entry_leading",
        symbol="QENIS",
        text="QENIS entry $0.0006, stop $0.00045, target $0.0011",
        truth=TokenTruth(address="q1", symbol="QENIS", price_usd=0.0006),
        expected=(
            ExpectedClaim("price", 0.0006, VERIFIED),
            ExpectedClaim("price", 0.00045, CONTRADICTED),
            ExpectedClaim("price", 0.0011, CONTRADICTED),
        ),
    ),

    # ── negative change via direction word, no symbol inline ───────────────
    Case(
        id="change_negative_no_symbol",
        symbol="BONK",
        text="down 12.4% in 24h after the dump",
        truth=TokenTruth(address="a1", symbol="BONK", change_24h=-12.4),
        expected=(ExpectedClaim("change_24h", -12.4, VERIFIED),),
    ),

    # ── age phrasings ───────────────────────────────────────────────────────
    Case(
        id="age_days_old",
        symbol="BONK",
        text="launched 21 days old",
        truth=TokenTruth(address="a1", symbol="BONK", age_seconds=21 * 86400),
        expected=(ExpectedClaim("age_days", 21, VERIFIED),),
    ),
    Case(
        id="age_d_ago",
        symbol="BONK",
        text="BONK created 2d ago",
        truth=TokenTruth(address="a1", symbol="BONK", age_seconds=2 * 86400),
        expected=(ExpectedClaim("age_days", 2, VERIFIED),),
    ),

    # ── noun AFTER the figure (canonical) ──────────────────────────────────
    Case(
        id="money_noun_after",
        symbol="BONK",
        text="$608.6K mcap, $269.3K volume, $80.4K liquidity, $500K FDV",
        truth=TokenTruth(
            address="a1", symbol="BONK",
            market_cap=608_600, volume_usd=269_300, liquidity_usd=80_400, fdv=500_000,
        ),
        expected=(
            ExpectedClaim("market_cap", 608_600, VERIFIED),
            ExpectedClaim("volume", 269_300, VERIFIED),
            ExpectedClaim("liquidity", 80_400, VERIFIED),
            ExpectedClaim("fdv", 500_000, VERIFIED),
        ),
    ),

    # ── noun BEFORE the figure (very common in agent prose) ────────────────
    Case(
        id="money_noun_before",
        symbol="BONK",
        text="mcap $608.6K · volume $269.3K · liquidity $80.4K · FDV $500K",
        truth=TokenTruth(
            address="a1", symbol="BONK",
            market_cap=608_600, volume_usd=269_300, liquidity_usd=80_400, fdv=500_000,
        ),
        expected=(
            ExpectedClaim("market_cap", 608_600, VERIFIED),
            ExpectedClaim("volume", 269_300, VERIFIED),
            ExpectedClaim("liquidity", 80_400, VERIFIED),
            ExpectedClaim("fdv", 500_000, VERIFIED),
        ),
    ),

    # ── ratio phrasings ─────────────────────────────────────────────────────
    Case(
        id="ratio_x_vol_liq",
        symbol="BONK",
        text="3.3x vol/liq",
        truth=TokenTruth(
            address="a1", symbol="BONK", volume_usd=269_300, liquidity_usd=80_400,
        ),
        expected=(ExpectedClaim("volume_liquidity_ratio", 3.3, VERIFIED),),
    ),
    Case(
        id="ratio_x_ratio",
        symbol="BONK",
        text="3.3x ratio",
        truth=TokenTruth(
            address="a1", symbol="BONK", volume_usd=269_300, liquidity_usd=80_400,
        ),
        expected=(ExpectedClaim("volume_liquidity_ratio", 3.3, VERIFIED),),
    ),

    # ── magnitude suffixes ──────────────────────────────────────────────────
    Case(
        id="magnitude_suffixes",
        symbol="BONK",
        text="$1.5B mcap · $170M volume · $1.2M liquidity · $500K FDV",
        truth=TokenTruth(
            address="a1", symbol="BONK",
            market_cap=1_500_000_000, volume_usd=170_000_000,
            liquidity_usd=1_200_000, fdv=500_000,
        ),
        expected=(
            ExpectedClaim("market_cap", 1_500_000_000, VERIFIED),
            ExpectedClaim("volume", 170_000_000, VERIFIED),
            ExpectedClaim("liquidity", 1_200_000, VERIFIED),
            ExpectedClaim("fdv", 500_000, VERIFIED),
        ),
    ),

    # ── thousands separators ────────────────────────────────────────────────
    Case(
        id="thousands_commas",
        symbol="BONK",
        text="mcap $1,234,567",
        truth=TokenTruth(address="a1", symbol="BONK", market_cap=1_234_567),
        expected=(ExpectedClaim("market_cap", 1_234_567, VERIFIED),),
    ),

    # ── multiple claims of the same metric ──────────────────────────────────
    Case(
        id="multiple_prices",
        symbol="QENIS",
        text="QENIS current $0.0006, target $0.0011",
        truth=TokenTruth(address="q1", symbol="QENIS", price_usd=0.0006),
        expected=(
            ExpectedClaim("price", 0.0006, VERIFIED),
            ExpectedClaim("price", 0.0011, CONTRADICTED),
        ),
    ),

    # ── change windows ──────────────────────────────────────────────────────
    Case(
        id="change_in_the_last_24h",
        symbol="BONK",
        text="+5.2% in the last 24h",
        truth=TokenTruth(address="a1", symbol="BONK", change_24h=5.2),
        expected=(ExpectedClaim("change_24h", 5.2, VERIFIED),),
    ),
    Case(
        id="change_1d_alias",
        symbol="BONK",
        text="+5.2% 1d",
        truth=TokenTruth(address="a1", symbol="BONK", change_24h=5.2),
        expected=(ExpectedClaim("change_24h", 5.2, VERIFIED),),
    ),
    Case(
        id="change_6h",
        symbol="BONK",
        text="+1.1% 6h",
        truth=TokenTruth(address="a1", symbol="BONK", change_6h=1.1),
        expected=(ExpectedClaim("change_6h", 1.1, VERIFIED),),
    ),

    # ── inline token symbol, no default token ───────────────────────────────
    Case(
        id="inline_symbol",
        symbol="",
        text="WIF +8.9% 1h and $420K volume",
        truth=TokenTruth(address="w1", symbol="WIF", change_1h=8.9, volume_usd=420_000),
        expected=(
            ExpectedClaim("change_1h", 8.9, VERIFIED),
            ExpectedClaim("volume", 420_000, VERIFIED),
        ),
    ),
]


# Inputs the engine currently does NOT handle. Shown in the report for honesty;
# they are intentionally excluded from the scored dataset.
KNOWN_LIMITATIONS: list[KnownLimitation] = [
    KnownLimitation(
        id="negation",
        symbol="BONK",
        text="BONK is not $500K, it is $250K",
        truth=TokenTruth(address="a1", symbol="BONK", market_cap=250_000),
        note="negation is not parsed: both figures are extracted as positive claims",
    ),
    KnownLimitation(
        id="forecast",
        symbol="BONK",
        text="BONK will hit $0.01 next month",
        truth=TokenTruth(address="a1", symbol="BONK", price_usd=0.000002907),
        note="forecasts/targets are treated as current facts, so a legit plan can be flagged CONTRADICTED",
    ),
]
