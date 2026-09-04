"""claimchain - verify that an AI agent's on-chain claims are actually true.

This is a claim-level "groundedness" checker for Solana / memecoin trading
analysis. It extracts every concrete number an agent states, fetches the real
on-chain data from free public APIs (DexScreener), and adjudicates each claim
as VERIFIED, CONTRADICTED, or UNRESOLVED - plus an overall 0-100 score.

Typical use::

    from claimchain import DexScreenerProvider, verify_text

    agent_text = "Max Rocket: QENIS +3.1% 1h, $608.6K mcap, 3.3x vol/liq"
    truth, report = verify_text(agent_text, symbol="QENIS")
    print(report)
"""

from __future__ import annotations

from typing import Optional, Tuple

from .extract import Claim, extract_claims
from .providers import DexScreenerProvider, StaticProvider, TokenTruth
from .report import render
from .verify import VerdictSet, verify_claims
from ._version import __version__

__all__ = [
    "Claim",
    "DexScreenerProvider",
    "StaticProvider",
    "TokenTruth",
    "VerdictSet",
    "extract_claims",
    "verify_claims",
    "verify_text",
]


def verify_text(
    text: str,
    symbol: Optional[str] = None,
    address: Optional[str] = None,
    provider: Optional[object] = None,
    output_format: str = "table",
) -> Tuple[Optional[TokenTruth], str]:
    """Verify every numeric claim in ``text`` against live on-chain data.

    ``symbol`` names the coin the analysis is about (used to resolve ground
    truth and to tag claims that don't name the token inline). ``address`` is a
    mint address, which takes precedence over ``symbol``.
    """

    provider = provider or DexScreenerProvider()

    truth = None
    if address:
        truth = provider.get_token(address)  # type: ignore[attr-defined]
    elif symbol:
        truth = provider.search(symbol)  # type: ignore[attr-defined]

    claims = extract_claims(text, default_token=symbol or (truth.symbol if truth else None))
    result = verify_claims(claims, truth)
    return truth, render(result, output_format)
