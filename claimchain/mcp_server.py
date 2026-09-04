"""Model Context Protocol (MCP) server for claimchain.

Exposes on-chain claim verification as MCP tools so any MCP-speaking agent —
Claude Desktop, Cursor, Claude Code, a browser-use agent, a trading "crew" —
can check whether the numbers in an AI analysis are actually true before it
repeats them.

The transport is the simplest MCP transport there is: stdio, JSON-RPC 2.0,
one message per line. No third-party ``mcp`` package is required; this module
uses only the standard library, like the rest of claimchain.

Tools
-----
``verify_claims``
    Extract every falsifiable number from ``text``, resolve the token's ground
    truth, and return a per-claim verdict (VERIFIED / CONTRADICTED /
    UNRESOLVED) plus a 0-100 groundedness score.

``token_snapshot``
    Return the live normalized ground-truth snapshot for a symbol or mint
    address (the same data the verifier compares against).

Run it with::

    claimchain --mcp            # from a shell
    python -m claimchain.mcp_server
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional, TextIO

from . import __version__
from .extract import extract_claims
from .providers import DexScreenerProvider, TokenTruth
from .report import render
from .verify import verify_claims

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "claimchain"

TOOLS = [
    {
        "name": "verify_claims",
        "description": (
            "Verify every numeric claim in an AI agent's analysis against live "
            "on-chain data. Extracts price-change %, market cap, FDV, liquidity, "
            "volume, price, pool age and vol/liq ratio, then adjudicates each as "
            "VERIFIED, CONTRADICTED or UNRESOLVED and returns a 0-100 groundedness "
            "score. Use this before trusting or reposting an agent's token call."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The agent's analysis text containing the claims.",
                },
                "symbol": {
                    "type": "string",
                    "description": "Ticker to resolve (e.g. QENIS). Used when claims do not name the token inline.",
                },
                "address": {
                    "type": "string",
                    "description": "Mint address; takes precedence over symbol.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "token_snapshot",
        "description": (
            "Fetch the live ground-truth snapshot for a token by symbol or mint "
            "address: price, 5m/1h/6h/24h change, volume, liquidity, market cap, "
            "FDV and age, normalized from DexScreener."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker (e.g. BONK)."},
                "address": {"type": "string", "description": "Mint address; takes precedence over symbol."},
            },
        },
    },
]


def _truth_dict(truth: TokenTruth) -> Dict[str, Any]:
    """Serialize a :class:`TokenTruth` snapshot to a JSON-friendly dict."""
    return {
        "address": truth.address,
        "symbol": truth.symbol,
        "name": truth.name,
        "price_usd": truth.price_usd,
        "change_5m": truth.change_5m,
        "change_1h": truth.change_1h,
        "change_6h": truth.change_6h,
        "change_24h": truth.change_24h,
        "volume_usd": truth.volume_usd,
        "liquidity_usd": truth.liquidity_usd,
        "market_cap": truth.market_cap,
        "fdv": truth.fdv,
        "age_days": truth.age_days,
        "dex": truth.dex,
    }


def _resolve(provider: Any, symbol: Optional[str], address: Optional[str]) -> Optional[TokenTruth]:
    if address:
        return provider.get_token(address)
    if symbol:
        return provider.search(symbol)
    return None


def _call_tool(name: str, arguments: Dict[str, Any], provider: Any) -> str:
    if name == "verify_claims":
        text = (arguments.get("text") or "").strip()
        if not text:
            raise ValueError("'text' is required and must not be empty")
        symbol = arguments.get("symbol")
        address = arguments.get("address")
        truth = _resolve(provider, symbol, address)
        claims = extract_claims(text, default_token=symbol or (truth.symbol if truth else None))
        result = verify_claims(claims, truth)
        return render(result, "json")

    if name == "token_snapshot":
        symbol = arguments.get("symbol")
        address = arguments.get("address")
        if not symbol and not address:
            raise ValueError("provide 'symbol' or 'address'")
        truth = _resolve(provider, symbol, address)
        if truth is None:
            return json.dumps({"error": "token not found", "symbol": symbol, "address": address})
        return json.dumps(_truth_dict(truth), indent=2)

    raise ValueError(f"unknown tool: {name}")


def _rpc_result(msg_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _rpc_error(msg_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": msg_id, "error": err}


def _initialize_result() -> Dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": __version__},
    }


def handle_message(msg: Dict[str, Any], provider: Any) -> Optional[Dict[str, Any]]:
    """Handle one JSON-RPC message and return the response (or ``None``).

    ``provider`` is any object with ``search(symbol)`` and ``get_token(address)``,
    so tests can inject a :class:`~claimchain.providers.StaticProvider` and run
    the whole protocol offline.
    """
    method = msg.get("method")
    msg_id = msg.get("id")

    # Notifications carry no id and expect no response.
    if msg_id is None:
        return None

    try:
        if method == "initialize":
            return _rpc_result(msg_id, _initialize_result())
        if method == "ping":
            return _rpc_result(msg_id, {})
        if method == "tools/list":
            return _rpc_result(msg_id, {"tools": TOOLS})
        if method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            text = _call_tool(name, arguments, provider)
            return _rpc_result(msg_id, {"content": [{"type": "text", "text": text}], "isError": False})
        return _rpc_error(msg_id, -32601, f"method not found: {method}")
    except ValueError as exc:  # bad tool arguments
        return _rpc_result(
            msg_id,
            {"content": [{"type": "text", "text": str(exc)}], "isError": True},
        )
    except Exception as exc:  # pragma: no cover - network/unknown failures
        return _rpc_result(
            msg_id,
            {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True},
        )


def serve(provider: Any = None, stdin: Optional[TextIO] = None, stdout: Optional[TextIO] = None) -> int:
    """Run the stdio JSON-RPC loop until stdin closes. Returns a process exit code."""
    provider = provider or DexScreenerProvider()
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue  # ignore unparseable lines; never crash the loop
        response = handle_message(msg, provider)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
    return 0


def main() -> int:
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
