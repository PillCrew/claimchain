"""Offline demo: verify a fabricated agent verdict against a known snapshot.

Run with the virtualenv python:  python examples/demo.py
"""

from claimchain import StaticProvider, TokenTruth, verify_text

# A stand-in for DexScreener ground truth. In production claimchain fetches
# this automatically from the live API.
qenis = TokenTruth(
    address="QENISaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    symbol="QENIS",
    name="Qenis",
    price_usd=0.0006,
    change_1h=3.1,
    change_24h=5.0,
    volume_usd=269_300,
    liquidity_usd=80_400,
    market_cap=608_600,
    age_seconds=19.5 * 86400,
)

agent_text = (
    "THE CREW VERDICT: Qenis is the pick. It's up +3.1% in the last hour and "
    "+5.0% over 24h with a healthy 3.3x vol/liq ratio. $269.3K volume on an "
    "$80.4K pool, $608.6K mcap. Entry $0.0006, target $0.00085. "
    "The only exit liquidity is my bank account."  # a memey claim, ignore
)

truth, report = verify_text(agent_text, symbol="QENIS", provider=StaticProvider({"qenis": qenis}))
print(report)
