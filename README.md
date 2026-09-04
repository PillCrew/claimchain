# claimchain

[![CI](https://github.com/PillCrew/claimchain/actions/workflows/ci.yml/badge.svg)](https://github.com/PillCrew/claimchain/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/claimchain)](https://pypi.org/project/claimchain/)
[![license](https://img.shields.io/github/license/PillCrew/claimchain)](LICENSE)

**Verify that an AI agent's on-chain claims are actually true.**

> **[Try it live](https://pillcrew.github.io/claimchain/) — no install, no API key.**
> Paste an agent's token call and watch every number get adjudicated against the
> real DexScreener data in your browser.

`claimchain` is a claim-level "groundedness" checker for Solana / memecoin trading
agents. It extracts every concrete number an AI agent states, fetches the real
on-chain data from free public APIs, and adjudicates each claim as
**VERIFIED**, **CONTRADICTED**, or **UNRESOLVED** — plus an overall score from
0–100 telling you how much of the agent's analysis is actually real.

Bullish AI agents are flooding X with token calls. The problem: they
**hallucinate numbers**. A "crew" of agents will confidently write:

> `+3.1% 1h · $608.6K mcap · 3.3x vol/liq · 19.5d old · entry $0.0006`

…and half of those numbers are made up, stale, or wrong. There is no check —
anyone who posts those numbers is implicitly trusted. `claimchain` is the check.

> **Why it's novel.** Searches for Solana *claim* verifiers, agent benchmark
> harnesses for trading, and hallucination/fact-check tooling for crypto claims
> return essentially nothing. The ecosystem is crowded with *risk oracles*,
> *sniping bots*, and *agent frameworks* — but nobody verifies **the agent's own
> words** against chain data. This is that tool.

---

## Install

```bash
pip install claimchain
```

Or from source (zero runtime dependencies, Python ≥ 3.9):

```bash
git clone https://github.com/PillCrew/claimchain.git
cd claimchain
pip install -e .[dev]
pytest
```

The data layer uses only the standard library (`urllib`) and the free, keyless
**DexScreener** public API — no API key, no paid feed, no dependencies.

---

## Live demo

The whole pipeline also runs **in your browser**:

* [**pillcrew.github.io/claimchain**](https://pillcrew.github.io/claimchain/)

It's a self-contained page (zero build step, zero dependencies) that ports the
extractor and verdict engine to JavaScript and calls DexScreener directly.
Source lives in [`docs/index.html`](docs/index.html) and is pinned by
`tests/js_core_test.js` in CI, so the Python and JavaScript engines can't drift
apart.

---

## Quickstart

### CLI

```bash
# Verify a single verdict against a mint address
claimchain --address DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263 \
  --file examples/bonk.txt

# Or resolve by ticker
claimchain --symbol QENIS --text "QENIS +3.1% 1h, \$608.6K mcap, 3.3x vol/liq"

# Machine-readable output for CI / auto-posting
claimchain --symbol QENIS --file verdict.txt --json

# Tune tolerances (percent-points for changes, relative for dollars)
claimchain --symbol QENIS --file verdict.txt --percent-pp 1.5 --relative 0.15
```

### Python API

```python
from claimchain import DexScreenerProvider, verify_text

text = "QENIS +3.1% 1h, $608.6K mcap, 3.3x vol/liq, 19.5d old"
truth, report = verify_text(text, symbol="QENIS")   # resolves live data
print(report)

# Fully offline / deterministic (great for tests):
from claimchain import StaticProvider, TokenTruth
qenis = TokenTruth(address="...", symbol="QENIS", change_1h=3.1,
                   market_cap=608_600, volume_usd=269_300, liquidity_usd=80_400,
                   age_seconds=19.5 * 86400)
truth, report = verify_text(text, symbol="QENIS", provider=StaticProvider({"q": qenis}))
```

---

## Example output

```
TOKEN: Bonk
------------------------------------------------------------------------------
METRIC                 CLAIM                  ACTUAL                 VERDICT
------------------------------------------------------------------------------
market_cap             $1.50B                 $256.02M               NO  CONTRADICTED
volume                 $170.00M               $125.93K               NO  CONTRADICTED
liquidity              $1.20M                 $199.59K               NO  CONTRADICTED
price                  $0.00005               $0.000003              NO  CONTRADICTED
age_days               1347.0d                1347.4d                OK  VERIFIED
volume_liquidity_ratio 141.00x                0.63x                  NO  CONTRADICTED
------------------------------------------------------------------------------
GROUNDEDNESS SCORE: 17/100 (OK 1 | NO 5 | ? 0)
```

A low score means the agent is **fabricating**. The tool catches it before it
reaches the timeline.

---

## How it works

```
 agent text ──▶ extract ──▶ resolve ──▶ verify ──▶ report
                claims       token       per-claim    table / JSON
                (regex)      snapshot    verdict      + score
```

1. **Extract** (`claimchain/extract.py`) — pulls every falsifiable number from
   the prose: price-change %, market cap, liquidity, volume, FDV, price, pool
   age, and vol/liq ratio. Handles `K`/`M`/`B` suffixes and `5m/1h/6h/24h`
   windows.
2. **Resolve** (`claimchain/providers.py`) — fetches the token's ground truth
   from DexScreener (or an injected `StaticProvider` for tests). Picks the best
   DEX pair (preferring Solana-native DEXes, then real 24h volume) and reads
   volume from `volume.h24`.
3. **Verify** (`claimchain/verify.py`) — compares each claim to reality with a
   tolerance: ±percentage-points for changes, relative tolerance for dollars.
   Issues VERIFIED / CONTRADICTED / UNRESOLVED.
4. **Report** (`claimchain/report.py`) — renders a monospace table or JSON, plus
   the **groundedness score** (share of claims that are true).

### Groundedness score

`score = 100 × (VERIFIED / total)`. A 100 means every claim was true; a 17 means
the agent mostly made it up. Plug this number into your agent's output and let
the community see *why* to trust (or not trust) a call.

---

## Solo-validator vs. multi-agent

`claimchain` is built for multi-agent "crew" setups. Each agent's claims are
adjudicated independently, so you can score **Max**, **Dr. Delta**, and
**Prof. HODL** separately and highlight whose numbers are real. It plugs into an
[ElizaOS](https://github.com/elizaOS/eliza)/ai16z plugin or a small extraction
loop in a Next.js backend in minutes.

---

## Use it from any agent (MCP)

`claimchain` ships a zero-dependency **Model Context Protocol** server, so any
MCP-speaking agent — Claude Desktop, Cursor, Claude Code, a browser-use agent,
your own trading "crew" — can check a claim against the chain before it trusts
or reposts it. No `mcp` package, no daemon: just stdio JSON-RPC.

```bash
claimchain --mcp            # or: python -m claimchain.mcp_server
```

Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "claimchain": {
      "command": "claimchain",
      "args": ["--mcp"]
    }
  }
}
```

Two tools are exposed:

* `verify_claims(text, symbol?, address?)` — extract every number in the text,
  adjudicate each against live chain data, and return the verdicts plus the
  0–100 groundedness score.
* `token_snapshot(symbol?, address?)` — the normalized live snapshot (price,
  changes, volume, liquidity, market cap, FDV, age) the verifier compares
  against.

This is the only Solana-flavored MCP tool that fact-checks **the agent's own
words** — the rest of the ecosystem exposes trading, risk, and payment tools.

---

## Benchmark

Extraction is the part most likely to quietly regress, so the repo ships a
deterministic, offline benchmark harness (`benchmarks/`) that scores the
extractor and the verdict engine against a labeled dataset of 18 claim
patterns — including the tricky ones: noun-before-figure money
(`"mcap $608.6K · volume $269.3K"`), comma-separated thousands
(`"$1,234,567"`), direction words (`"down 12.4% in 24h"`), `"in the last 24h"`
windows, `1d` aliases, and `K/M/B` magnitude suffixes.

Run it with:

```bash
python -m benchmarks.runner
```

Current measured score:

| metric                  | value   |
| ----------------------- | ------- |
| cases                   | 18      |
| extraction precision    | 1.000   |
| extraction recall       | 1.000   |
| extraction F1           | 1.000   |
| verdict accuracy        | 1.000   |
| case pass rate          | 1.000   |

The same thresholds are pinned as a CI gate in `tests/test_benchmark.py`, so a
change that breaks a documented claim pattern fails the suite. Two patterns are
tracked as **known limitations** (deliberately not scored): negation
(`"not -5%"`) and forecast prices (`"target $0.0001"`), which the engine
currently treats as positive/current facts.

---

## Project status

`claimchain` is the blockchain-facing half of PillCrew's agent truthfulness
tooling. It is a deterministic, zero-runtime-dependency verifier with a live
DexScreener adapter, an offline provider for reproducible tests, a CLI, an MCP
server, a browser demo, and a versioned benchmark. The repository reports
limitations explicitly rather than presenting heuristic extraction as semantic
understanding.

Live market data is inherently time-sensitive. Reproducible evaluation uses
`StaticProvider` and the committed benchmark cases; production verification
uses a timestamped snapshot and should be interpreted with the documented
tolerances.

---

## Limitations (honest)

* Heuristic extraction — it matches numbers, not semantics. A claim phrased in a
  way the regex doesn't cover is silently skipped rather than called wrong.
* "Target" and "stop" prices are forecasts, not current facts; `claimchain`
  currently compares them to live price and may flag a legit plan as contradicted.
* Ground truth comes from one snapshot; extreme volatility can cause
  false CONTRADICTED near tolerance edges.
* Only covers the metrics DexScreener exposes (no holder counts, no buy/sell
  flow, no bundling data).

## Related: deedchain

`claimchain` is one half of PillCrew's *truthfulness suite*. Its sibling,
[**deedchain**](https://github.com/PillCrew/deedchain), measures **report
fidelity** for browser agents: does the agent's final report tell the truth
about what it actually *did* — what it clicked, opened, typed, and observed?
`claimchain` checks the claims; `deedchain` checks the deeds.

> *claimchain checks the claims. deedchain checks the deeds.*

Both projects are zero-runtime-dependency and use the same high-level
`extract → adjudicate → score` model, but they verify different evidence:
`claimchain` checks statements about live token data while `deedchain` checks
statements about browser actions against frozen ground truth.

## Contributing

PRs welcome. Keep the core dependency-free and add tests (`tests/`) for any new
extraction rule or metric.

## License

MIT — see [LICENSE](LICENSE).
