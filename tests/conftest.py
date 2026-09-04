"""Shared test fixtures: a realistic token snapshot and a static provider."""

import pytest

from claimchain.providers import StaticProvider, TokenTruth


@pytest.fixture
def qenis_truth() -> TokenTruth:
    return TokenTruth(
        address="QENISaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        symbol="QENIS",
        name="Qenis",
        price_usd=0.0006,
        change_5m=2.0,
        change_1h=3.1,
        change_6h=1.0,
        change_24h=5.0,
        volume_usd=269_300,
        liquidity_usd=80_400,
        market_cap=608_600,
        fdv=608_600,
        age_seconds=19.5 * 86400,
        dex="pumpfun",
    )


@pytest.fixture
def static_provider(qenis_truth) -> StaticProvider:
    return StaticProvider({"qenis": qenis_truth})
