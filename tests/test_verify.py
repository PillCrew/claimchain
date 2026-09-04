"""Tests for the verification engine (claim -> ground truth adjudication)."""

from claimchain.extract import Claim
from claimchain.verify import (
    CONTRADICTED,
    UNRESOLVED,
    VERIFIED,
    verify_claim,
    verify_claims,
)

import pytest


def test_verified_percent_within_tolerance(qenis_truth):
    claim = Claim(id="c1", metric="change_1h", value=3.1, token_symbol="QENIS")
    verdict = verify_claim(claim, qenis_truth)
    assert verdict.verdict == VERIFIED
    assert verdict.actual == 3.1


def test_contradicted_percent_out_of_tolerance(qenis_truth):
    claim = Claim(id="c2", metric="change_1h", value=10.0, token_symbol="QENIS")
    verdict = verify_claim(claim, qenis_truth)
    assert verdict.verdict == CONTRADICTED
    assert verdict.actual == 3.1
    assert verdict.diff_percent == 10.0 - 3.1


def test_verified_dollar_within_relative_tolerance(qenis_truth):
    claim = Claim(id="c3", metric="market_cap", value=608_600, token_symbol="QENIS")
    assert verify_claim(claim, qenis_truth).verdict == VERIFIED


def test_contradicted_dollar_out_of_tolerance(qenis_truth):
    claim = Claim(id="c4", metric="market_cap", value=5_000_000, token_symbol="QENIS")
    assert verify_claim(claim, qenis_truth).verdict == CONTRADICTED


def test_age_days_translated_from_seconds(qenis_truth):
    claim = Claim(id="c5", metric="age_days", value=19.5, token_symbol="QENIS")
    assert verify_claim(claim, qenis_truth).verdict == VERIFIED


def test_volume_liquidity_ratio_computed(qenis_truth):
    claim = Claim(id="c6", metric="volume_liquidity_ratio", value=3.3, token_symbol="QENIS")
    verdict = verify_claim(claim, qenis_truth)
    assert verdict.verdict == VERIFIED
    # 269300 / 80400 = 3.3495..., within 20%.
    assert verdict.actual == pytest.approx(3.3495, rel=1e-3)


def test_unresolved_when_no_truth():
    claim = Claim(id="c7", metric="market_cap", value=10_000)
    assert verify_claim(claim, None).verdict == UNRESOLVED


def test_volume_resolved_via_volume_usd(qenis_truth):
    claim = Claim(id="v1", metric="volume", value=269_300, token_symbol="QENIS")
    assert verify_claim(claim, qenis_truth).verdict == VERIFIED


def test_liquidity_resolved_via_liquidity_usd(qenis_truth):
    claim = Claim(id="l1", metric="liquidity", value=80_400, token_symbol="QENIS")
    assert verify_claim(claim, qenis_truth).verdict == VERIFIED


def test_metric_not_provided_is_unresolved(qenis_truth):
    claim = Claim(id="m1", metric="change_2h", value=1.0)
    # change_2h is not a real metric -> no ground truth -> unresolved.
    assert verify_claim(claim, qenis_truth).verdict == UNRESOLVED


def test_score_counts_mixed(qenis_truth):
    claims = [
        Claim(id="a", metric="change_1h", value=3.1),
        Claim(id="b", metric="market_cap", value=608_600),
        Claim(id="c", metric="change_24h", value=99.0),
    ]
    set_ = verify_claims(claims, qenis_truth)
    assert set_.counts[VERIFIED] == 2
    assert set_.counts[CONTRADICTED] == 1
    # 2 of 3 verified -> 67/100.
    assert set_.score == 67


def test_empty_claims_score_100():
    set_ = verify_claims([], None)
    assert set_.score == 100
