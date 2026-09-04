"""Tests for the zero-dependency MCP server (offline, via a StaticProvider)."""

import json
from io import StringIO

import pytest

from claimchain.mcp_server import handle_message, serve


def _provider(qenis_truth):
    from claimchain.providers import StaticProvider

    return StaticProvider({"qenis": qenis_truth})


def test_initialize_returns_server_info_and_tools_capability(qenis_truth):
    resp = handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        _provider(qenis_truth),
    )
    assert resp["id"] == 1
    result = resp["result"]
    assert result["protocolVersion"] == "2024-11-05"
    assert result["capabilities"] == {"tools": {}}
    assert result["serverInfo"]["name"] == "claimchain"


def test_tools_list_exposes_verify_claims_and_token_snapshot(qenis_truth):
    resp = handle_message(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        _provider(qenis_truth),
    )
    names = sorted(t["name"] for t in resp["result"]["tools"])
    assert names == ["token_snapshot", "verify_claims"]


def test_tools_call_verify_claims_returns_verdict_json(qenis_truth):
    text = "QENIS +3.1% 1h and a $5,000,000 market cap"
    resp = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "verify_claims", "arguments": {"text": text, "symbol": "QENIS"}},
        },
        _provider(qenis_truth),
    )
    assert resp["result"]["isError"] is False
    content = resp["result"]["content"]
    assert len(content) == 1 and content[0]["type"] == "text"
    payload = json.loads(content[0]["text"])
    # 3.1% 1h is within tolerance; $5M mcap is contradicted vs $608.6K.
    verdicts = {v["metric"]: v["verdict"] for v in payload["claims"]}
    assert verdicts["change_1h"] == "VERIFIED"
    assert verdicts["market_cap"] == "CONTRADICTED"
    assert payload["score"] == 50


def test_tools_call_token_snapshot_returns_normalized_truth(qenis_truth):
    resp = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "token_snapshot", "arguments": {"symbol": "qenis"}},
        },
        _provider(qenis_truth),
    )
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["symbol"] == "QENIS"
    assert payload["change_1h"] == pytest.approx(3.1)
    assert "volume_liquidity_ratio" not in payload  # snapshot is raw fields, not derived


def test_tools_call_bad_arguments_is_error(qenis_truth):
    resp = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "token_snapshot", "arguments": {}},
        },
        _provider(qenis_truth),
    )
    assert resp["result"]["isError"] is True


def test_unknown_method_returns_jsonrpc_error(qenis_truth):
    resp = handle_message(
        {"jsonrpc": "2.0", "id": 6, "method": "does/not/exist"},
        _provider(qenis_truth),
    )
    assert resp["error"]["code"] == -32601


def test_notification_returns_none(qenis_truth):
    # Notifications have no id -> the loop must not emit a response.
    resp = handle_message(
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        _provider(qenis_truth),
    )
    assert resp is None


def test_serve_loop_end_to_end(qenis_truth):
    request = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "verify_claims",
                "arguments": {"text": "QENIS is 19.5 days old", "symbol": "QENIS"},
            },
        }
    )
    out = StringIO()
    code = serve(_provider(qenis_truth), stdin=StringIO(request + "\n"), stdout=out)
    assert code == 0
    lines = [l for l in out.getvalue().splitlines() if l.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["id"] == 7
    assert payload["result"]["isError"] is False
