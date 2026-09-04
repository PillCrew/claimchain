"""Tests for provider normalization and pair selection."""

from claimchain.providers import DexScreenerProvider, StaticProvider, TokenTruth


def test_volume_falls_back_to_h24_when_usd_empty():
    pair = {
        "baseToken": {"address": "abc", "symbol": "BONK", "name": "Bonk"},
        "priceUsd": "0.000003",
        "priceChange": {"m5": "0.1", "h1": "0.5", "h6": "1.0", "h24": "2.0"},
        "volume": {"h24": "125162.5"},  # note: no "usd"
        "liquidity": {"usd": "199616.13"},
        "marketCap": "256131523",
        "fdv": "256131523",
        "pairCreatedAt": 1671980424000,
        "dexId": "orca",
    }
    truth = DexScreenerProvider._normalize(pair)
    assert truth.volume_usd == 125162.5
    assert truth.liquidity_usd == 199616.13
    assert truth.market_cap == 256131523


def test_best_pair_prefers_complete_snapshot():
    thin = {"liquidity": {"usd": "999999"}, "volume": {}, "marketCap": None, "priceUsd": None}
    rich = {"liquidity": {"usd": "100"}, "volume": {"usd": "500"}, "marketCap": "1000", "priceUsd": "0.1"}
    assert DexScreenerProvider._best_pair([thin, rich]) == rich


def test_best_pair_prefers_solana_native_over_wrapped():
    # A wrapped pair with huge liquidity but zero real volume must not beat
    # the Solana-native pair with real 24h volume.
    wrapped = {
        "dexId": "uniswap",
        "liquidity": {"usd": "344130349"},
        "volume": {"h24": "0.01"},
        "marketCap": "688260698",
        "priceUsd": "0.006882",
    }
    native = {
        "dexId": "orca",
        "liquidity": {"usd": "199550"},
        "volume": {"h24": "127320.68"},
        "marketCap": "255887307",
        "priceUsd": "0.000002907",
    }
    assert DexScreenerProvider._best_pair([wrapped, native]) == native


def test_normalize_prefers_h24_volume_over_short_window_usd():
    pair = {
        "baseToken": {"address": "abc", "symbol": "T", "name": "T"},
        "priceUsd": "0.001",
        "priceChange": {"h24": "1.0"},
        "volume": {"usd": "0.01", "h24": "45015.33"},  # usd = 5m window
        "liquidity": {"usd": "100000"},
        "marketCap": "500000",
        "pairCreatedAt": 1671980424000,
        "dexId": "raydium",
    }
    truth = DexScreenerProvider._normalize(pair)
    assert truth.volume_usd == 45015.33


def test_static_provider_resolves_by_symbol_and_address():
    t = TokenTruth(address="abc", symbol="QENIS", volume_usd=100, liquidity_usd=50)
    provider = StaticProvider({"q": t})
    assert provider.get_token("abc") is t
    assert provider.search("QENIS") is t
    assert provider.search("nope") is None


def test_volume_liquidity_ratio_property():
    t = TokenTruth(address="x", symbol="T", volume_usd=100, liquidity_usd=50)
    assert t.volume_liquidity_ratio == 2.0
