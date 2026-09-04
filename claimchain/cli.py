"""Command-line interface for claimchain.

Reads an agent's analysis (file or stdin), verifies it against live on-chain
data, and prints a verdict table (or JSON).

Examples::

    claimchain --symbol QENIS --text "QENIS +3.1% 1h, $608K mcap, 3.3x vol/liq"
    cat verdict.txt | claimchain --symbol QENIS
    claimchain --symbol QENIS --file verdict.txt --json
    claimchain --mcp
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .extract import extract_claims
from .mcp_server import serve as serve_mcp
from .providers import DexScreenerProvider
from .report import render
from .verify import verify_claims


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claimchain",
        description="Adjudicate whether an AI agent's on-chain claims are TRUE.",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--text", help="inline agent analysis text")
    src.add_argument("--file", "--input", dest="file", help="read agent analysis from a file")
    p.add_argument("--symbol", help="coin symbol to resolve (e.g. QENIS)")
    p.add_argument("--address", "--mint", dest="address", help="mint address (takes precedence)")
    p.add_argument("--json", action="store_true", help="output JSON instead of a table")
    p.add_argument("--mcp", action="store_true",
                   help="run as a stdio Model Context Protocol (MCP) server")
    p.add_argument("--percent-pp", type=float, default=2.0,
                   help="tolerance in %% -points for change claims (default 2.0)")
    p.add_argument("--relative", type=float, default=0.20,
                   help="relative tolerance for dollar/scalar claims (default 0.20)")
    p.add_argument("--version", action="version", version=f"claimchain {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)

    if args.mcp:
        return serve_mcp()

    if args.text:
        text = args.text
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            text = fh.read()
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("claimchain: no input text provided", file=sys.stderr)
        return 2

    provider = DexScreenerProvider()
    truth = None
    if args.address:
        truth = provider.get_token(args.address)
    elif args.symbol:
        truth = provider.search(args.symbol)

    claims = extract_claims(text, default_token=args.symbol or (truth.symbol if truth else None))
    result = verify_claims(claims, truth, percent_pp=args.percent_pp, relative=args.relative)

    if args.json:
        print(render(result, "json"))
    else:
        print(render(result, "table"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
