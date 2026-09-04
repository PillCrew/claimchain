"""Data providers that fetch live on-chain ground truth for verification.

``claimchain`` never trusts the agent - it pulls the real numbers itself from
free, keyless public endpoints (DexScreener) and compares them against the
agent's claims. Every provider normalizes to the same :class:`TokenTruth` shape
so the verification engine is transport-agnostic (and fully testable offline).
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from ._version import __version__


@dataclass
class TokenTruth:
    """The ground-truth snapshot of a token, normalized from a data provider."""

    address: str
    symbol: str
    name: str = ""
    price_usd: Optional[float] = None
    change_5m: Optional[float] = None
    change_1h: Optional[float] = None
    change_6h: Optional[float] = None
    change_24h: Optional[float] = None
    volume_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None
    market_cap: Optional[float] = None
    fdv: Optional[float] = None
    age_seconds: Optional[float] = None
    dex: Optional[str] = None

    @property
    def age_days(self) -> Optional[float]:
        if self.age_seconds is None:
            return None
        return self.age_seconds / 86400.0

    @property
    def volume_liquidity_ratio(self) -> Optional[float]:
        if self.volume_usd is None or not self.liquidity_usd:
            return None
        return self.volume_usd / self.liquidity_usd


def _get_json(url: str, timeout: float = 15.0) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": f"claimchain/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _num(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


class DexScreenerProvider:
    """Fetches token ground truth from the free DexScreener public API."""

    BASE = "https://api.dexscreener.com/latest/dex"

    def get_token(self, address: str) -> Optional[TokenTruth]:
        url = f"{self.BASE}/tokens/{urllib.parse.quote(address)}"
        payload = _get_json(url)
        pairs = payload.get("pairs") or []
        if not pairs:
            return None
        return self._normalize(self._best_pair(pairs))

    def search(self, symbol: str) -> Optional[TokenTruth]:
        """Resolve a symbol to a token snapshot via DexScreener's search."""

        url = f"{self.BASE}/search?q={urllib.parse.quote(symbol)}"
        payload = _get_json(url)
        pairs = payload.get("pairs") or []
        if not pairs:
            return None
        return self._normalize(self._best_pair(pairs))

    # DexScreener's search spans every chain, so a Solana token can surface
    # wrapped pairs on Ethereum/BSC/etc. Those often report huge liquidity but
    # near-zero (or stale) volume, which would poison the snapshot. Prefer the
    # Solana-native pair, then real 24h volume, then liquidity.
    SOLANA_DEXES = {"orca", "raydium", "raydiumclmm", "meteora", "pumpfun", "moonshot"}

    @staticmethod
    def _best_pair(pairs: list) -> dict:
        """Pick the pair whose snapshot best represents the token.

        A token can trade across many DEX pairs, each reporting a different
        subset of fields. We want the Solana-native pair (this is a Solana
        tool) with the most real 24h volume, falling back to liquidity.
        """

        def key(p: dict) -> tuple:
            liq = _num((p.get("liquidity") or {}).get("usd")) or 0
            volume = p.get("volume") or {}
            vol = _num(volume.get("h24")) or _num(volume.get("usd")) or 0
            dex = (p.get("dexId") or "").lower()
            on_solana = 1 if dex in DexScreenerProvider.SOLANA_DEXES else 0
            return (on_solana, vol, liq)

        return max(pairs, key=key)

    @staticmethod
    def _normalize(pair: Dict[str, Any]) -> TokenTruth:
        base = pair.get("baseToken") or {}
        change = pair.get("priceChange") or {}
        volume = pair.get("volume") or {}
        liquidity = pair.get("liquidity") or {}
        created = _num(pair.get("pairCreatedAt"))
        now_ms = _num(time.time() * 1000)
        age = (now_ms - created) / 1000.0 if created and now_ms else None
        # ``volume.usd`` is a short-window (often 5m) snapshot; the 24h figure
        # in USD is the reliable flow metric, so prefer it when present.
        volume_usd = _num(volume.get("h24")) or _num(volume.get("usd"))
        return TokenTruth(
            address=base.get("address", ""),
            symbol=base.get("symbol", ""),
            name=base.get("name", ""),
            price_usd=_num(pair.get("priceUsd")),
            change_5m=_num(change.get("m5")),
            change_1h=_num(change.get("h1")),
            change_6h=_num(change.get("h6")),
            change_24h=_num(change.get("h24")),
            volume_usd=volume_usd,
            liquidity_usd=_num(liquidity.get("usd")),
            market_cap=_num(pair.get("marketCap")),
            fdv=_num(pair.get("fdv")),
            age_seconds=age,
            dex=pair.get("dexId"),
        )


class StaticProvider:
    """In-memory provider backed by a dict so verification can be tested offline."""

    def __init__(self, tokens: Dict[str, TokenTruth]) -> None:
        self._by_addr = {t.address: t for t in tokens.values()}
        self._by_sym = {t.symbol.upper(): t for t in tokens.values()}

    def get_token(self, address: str) -> Optional[TokenTruth]:
        return self._by_addr.get(address)

    def search(self, symbol: str) -> Optional[TokenTruth]:
        return self._by_sym.get(symbol.upper())
