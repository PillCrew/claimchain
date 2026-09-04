"""Extract structured, falsifiable claims from an agent's free-form analysis.

The goal is not to understand the prose - it is to pull out every concrete,
number-bearing assertion we can check against chain data. Each extracted
:class:`Claim` carries a metric, a signed value, the token it refers to (when
the symbol is named inline), and the raw snippet so a human can see exactly
what being adjudicated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# Canonical metric names used by the verification engine.
CHANGE_METRICS = {
    "5m": "change_5m",
    "1h": "change_1h",
    "6h": "change_6h",
    "24h": "change_24h",
    "1d": "change_24h",
    "day": "change_24h",
}


@dataclass
class Claim:
    id: str
    metric: str
    value: float
    token_symbol: Optional[str] = None
    token_address: Optional[str] = None
    raw: str = ""
    source: str = "text"

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"{self.metric}:{self.value}"

    def describe(self) -> str:
        unit = "%" if self.metric.startswith("change_") else ""
        suffix = f" {self.token_symbol}" if self.token_symbol else ""
        return f"{self.metric}{suffix} = {self.value:g}{unit}"


# Matches a token symbol/address token immediately before the number, but keeps
# the symbol optional so a claim can name the coin in a separate sentence.
_SYMBOL_BEFORE = r"([A-Z0-9][A-Z0-9._-]{1,15}|[1-9A-HJ-NP-Za-km-z]{32,44})"
_NUM = r"([+-]?\d+(?:\.\d+)?)"
# Direction words that flip/keep the sign of a percentage-change claim.
_DOWN = {"down", "fell", "dropped"}
_UP = {"up", "rose", "climbed"}

# "XYZ +3.2% (1h)", "XYZ -5% 24h", "+3.1% 1h", "down 12.4% in 24h",
# "+5.2% in the last 24h", "1h +3.1%"
# The symbol prefix is case-sensitive (tickers are uppercase by convention),
# while direction/window words use scoped case-insensitive groups. This keeps
# "down"/"up" from being swallowed by the symbol alternative.
_CHANGE_RE = re.compile(
    rf"(?:{_SYMBOL_BEFORE}\s+)?"
    rf"((?i:down|up|fell|rose|dropped|climbed))?\s*{_NUM}\s*%?"
    rf"\s*(?i:(?:in|over)\s+(?:the\s+)?(?:last\s+|past\s+)?)?"
    rf"((?i:5m|1h|6h|24h|1d|day))\b",
)

# "$372.4K", "$41.5K", "$608.6M", "$1,234,567", "$0.0006", "$200K"
# The K/M/B magnitude suffix must not be followed by another letter, otherwise
# the "m" in "$5,000,000 market cap" is eaten as an "M" magnitude and the claim
# is silently dropped.
_MONEY_DOLLAR = re.compile(
    r"\$\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(K|M|B)?(?!\w)",
    re.IGNORECASE,
)

# "<amount> days old", "<amount>d old", "<amount>d ago", "2 days ago".
# A bare "d" suffix is excluded: "1d" is far more likely a change window.
_AGE_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:day|days|d\s+(?:old|ago))\b",
    re.IGNORECASE,
)

# "3.3x vol/liq", "3.3x volume to liquidity", "3.3x ratio"
_VOL_LIQ_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*x\s*(?:"
    r"vol(?:ume)?\s*(?:/|to|:)\s*(?:liq(?:uidity)?)\s*(?:ratio)?"
    r"|vol(?:ume)?\s*/\s*liq(?:uidity)?"
    r"|ratio"
    r")",
    re.IGNORECASE,
)


def _split_units(value: float, unit: Optional[str]) -> float:
    if unit and unit.upper() == "K":
        return value * 1_000
    if unit and unit.upper() == "M":
        return value * 1_000_000
    if unit and unit.upper() == "B":
        return value * 1_000_000_000
    return value


def _find_symbol_prefix(text: str, end_pos: int) -> Optional[str]:
    """Look backwards from ``end_pos`` for a token symbol token."""

    prefix = text[:end_pos]
    m = re.search(r"([A-Z0-9][A-Z0-9._-]{1,15})\s*$", prefix)
    if m and not _is_stopword(m.group(1)):
        return m.group(1).upper()
    return None


_WORD_TOKENS = {
    "THE", "AND", "WITH", "FOR", "A", "AN", "ITS", "IS", "TO", "OF", "ON", "IN",
    "ENTRY", "TARGET", "STOP", "PRICE", "MCAP", "POOL", "LIQUIDITY", "VOLUME",
    "VOL", "FDV", "OLD", "DAY", "DAYS", "RATIO", "X", "AT", "BIG", "HIGHER",
}


def _is_stopword(tok: str) -> bool:
    return tok.upper() in _WORD_TOKENS


_CLIP_DELIMS = "$.,;:!?\n·|•—–"


def _clip_after(text: str, pos: int) -> str:
    """Text immediately following ``pos``, clipped at the next delimiter."""

    s = text[pos:pos + 16]
    cut = len(s)
    for ch in _CLIP_DELIMS:
        i = s.find(ch)
        if i != -1 and i < cut:
            cut = i
    return s[:cut].lower()


def _clip_before(text: str, pos: int) -> str:
    """Text immediately preceding ``pos``, clipped back to the last delimiter."""

    s = text[max(0, pos - 16):pos]
    cut = -1
    for ch in _CLIP_DELIMS:
        i = s.rfind(ch)
        if i > cut:
            cut = i
    return s[cut + 1:].lower()


def _classify_money(after: str, before: str, amount: float, unit: Optional[str]) -> Optional[str]:
    """Decide what a dollar figure refers to.

    The metric noun usually follows the amount (``"$608.6K mcap"``), but it
    often leads it too (``"mcap $608.6K"``, ``"FDV: $2.1B"``). We scan *after*
    first, then *before*, for every money noun plus the leading price hints.
    """

    def _has(*needles: str) -> bool:
        return any(n in after for n in needles)

    if _has("market cap", "marketcap", "mcap"):
        return "market_cap"
    if _has("fdv"):
        return "fdv"
    if _has("liquidity", "pool"):
        return "liquidity"
    if _has("volume") or re.search(r"\bvol\b", after):
        return "volume"
    if re.search(r"\bprice\b", after):
        return "price"
    # Noun BEFORE the figure: "mcap $608.6K", "FDV $500K", "volume $269.3K".
    if re.search(r"\b(?:market\s*cap|marketcap|mcap)\b", before):
        return "market_cap"
    if re.search(r"\bfdv\b", before):
        return "fdv"
    if re.search(r"\b(?:liquidity|pool)\b", before):
        return "liquidity"
    if re.search(r"\b(?:volume|vol)\b", before):
        return "volume"
    # Price hints can lead the amount ("entry $0.0006", "stop $x").
    if re.search(r"\b(entry|stop|target|invalidated|price)\b", before):
        return "price"
    # A bare small amount with no magnitude suffix is a token price (e.g. $0.0006).
    if unit is None and amount < 1.0:
        return "price"
    return None


def extract_claims(text: str, default_token: Optional[str] = None) -> List[Claim]:
    """Extract all falsifiable numeric claims from ``text``."""

    claims: List[Claim] = []

    def add(metric: str, value: float, raw: str, symbol: Optional[str], source: str = "text") -> None:
        claims.append(
            Claim(id=f"{metric}:{value:g}:{len(claims)}", metric=metric, value=value,
                  token_symbol=symbol or default_token, raw=raw, source=source)
        )

    # Percentage-change claims.
    for m in _CHANGE_RE.finditer(text):
        value = float(m.group(3))
        direction = (m.group(2) or "").lower()
        if direction in _DOWN:
            value = -abs(value)
        elif direction in _UP:
            value = abs(value)
        window = m.group(4).lower()
        metric = CHANGE_METRICS[window]
        # Use greedy symbol detection: prefer the named symbol if present.
        symbol = _find_symbol_prefix(text, m.start(3))
        add(metric, value, m.group(0).strip(), symbol)

    # Dollar denominated claims: mcap, liquidity, volume, price, fdv.
    # The metric word ("volume", "liquidity", "mcap") usually follows the amount,
    # e.g. "$372.4K volume", but it can also lead it ("mcap $608.6K"). Look
    # ahead (scoped to the clause), then fall back to the noun before the figure.
    for m in _MONEY_DOLLAR.finditer(text):
        amount = float(m.group(1).replace(",", ""))
        unit = m.group(2)
        value = _split_units(amount, unit)
        after = _clip_after(text, m.end())
        before = _clip_before(text, m.start())
        metric = _classify_money(after, before, amount, unit)
        if metric is None:
            continue
        symbol = _find_symbol_prefix(text, m.start())
        add(metric, value, m.group(0).strip(), symbol)

    # Age claims.
    for m in _AGE_RE.finditer(text):
        value = float(m.group(1))
        raw = m.group(0).strip()
        metric = "age_days"
        symbol = _find_symbol_prefix(text, m.start(1))
        add(metric, value, raw, symbol)

    # Volume / liquidity ratio claims.
    for m in _VOL_LIQ_RE.finditer(text):
        value = float(m.group(1))
        raw = m.group(0).strip()
        symbol = _find_symbol_prefix(text, m.start())
        add("volume_liquidity_ratio", value, raw, symbol)

    return claims
