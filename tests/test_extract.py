"""Tests for extracting structured claims from free-form agent text."""

from claimchain.extract import extract_claims


def _by_metric(claims, metric):
    return [c for c in claims if c.metric == metric]


def test_change_claim_with_inline_symbol():
    claims = extract_claims("QENIS +3.1% 1h")
    cs = _by_metric(claims, "change_1h")
    assert len(cs) == 1
    assert cs[0].value == 3.1
    assert cs[0].token_symbol == "QENIS"


def test_change_claim_negative_and_24h():
    claims = extract_claims("MANLET -39.7% 24h")
    cs = _by_metric(claims, "change_24h")
    assert len(cs) == 1
    assert cs[0].value == -39.7
    assert cs[0].token_symbol == "MANLET"


def test_money_claims_units():
    text = "GEOM's $372.4K volume, $41.5K liquidity, $608.6M mcap"
    claims = extract_claims(text)
    vol = _by_metric(claims, "volume")
    liq = _by_metric(claims, "liquidity")
    mcap = _by_metric(claims, "market_cap")
    assert vol and round(vol[0].value) == 372_400
    assert liq and round(liq[0].value) == 41_500
    assert mcap and round(mcap[0].value) == 608_600_000


def test_price_claim():
    claims = extract_claims("entry $0.0006, stop $0.00054")
    price = _by_metric(claims, "price")
    assert any(round(c.value, 6) == 0.0006 for c in price)
    assert any(round(c.value, 6) == 0.00054 for c in price)


def test_age_claim():
    claims = extract_claims("Qenis clears the gate at 19.5d old")
    age = _by_metric(claims, "age_days")
    assert age and age[0].value == 19.5


def test_vol_liq_ratio():
    claims = extract_claims("a 3.3x vol/liq ratio")
    ratio = _by_metric(claims, "volume_liquidity_ratio")
    assert ratio and ratio[0].value == 3.3


def test_default_token_used_when_none_named():
    claims = extract_claims("+3.1% 1h and $608.6K mcap", default_token="QENIS")
    assert all(c.token_symbol == "QENIS" for c in claims)


def test_realistic_verdict_passage():
    text = (
        "Dr. Delta: GEOM's $372.4K volume is the highest absolute number, but its "
        "$41.5K liquidity and -6.8% 1h fade make it a trap, while Qenis holds "
        "+3.1% 1h with a healthier 3.3x ratio."
    )
    claims = extract_claims(text)
    metrics = {c.metric for c in claims}
    assert {"volume", "liquidity", "change_1h", "volume_liquidity_ratio"} <= metrics
    # Two distinct change_1h claims: -6.8% (GEOM) and +3.1% (Qenis).
    h1 = _by_metric(claims, "change_1h")
    values = {round(c.value, 2) for c in h1}
    assert -6.8 in values and 3.1 in values


def test_money_noun_before_figure():
    text = "mcap $608.6K · volume $269.3K · liquidity $80.4K · FDV $500K"
    claims = extract_claims(text)
    assert round(_by_metric(claims, "market_cap")[0].value) == 608_600
    assert round(_by_metric(claims, "volume")[0].value) == 269_300
    assert round(_by_metric(claims, "liquidity")[0].value) == 80_400
    assert round(_by_metric(claims, "fdv")[0].value) == 500_000


def test_money_thousands_commas():
    claims = extract_claims("mcap $1,234,567")
    assert round(_by_metric(claims, "market_cap")[0].value) == 1_234_567


def test_money_thousands_commas_before_market_cap():
    # Regression: "m" in "market cap" must not be consumed as an M magnitude.
    claims = extract_claims("QENIS +3.1% 1h and a $5,000,000 market cap")
    mcap = _by_metric(claims, "market_cap")
    assert mcap and mcap[0].value == 5_000_000


def test_change_direction_word_sign():
    claims = extract_claims("down 12.4% in 24h after the dump")
    cs = _by_metric(claims, "change_24h")
    assert cs and cs[0].value == -12.4


def test_change_in_the_last_window():
    claims = extract_claims("+5.2% in the last 24h")
    cs = _by_metric(claims, "change_24h")
    assert cs and cs[0].value == 5.2


def test_change_1d_is_not_age():
    claims = extract_claims("+5.2% 1d")
    assert _by_metric(claims, "change_24h")
    assert not _by_metric(claims, "age_days")
