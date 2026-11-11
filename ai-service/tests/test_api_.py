import pytest
from fastapi.testclient import TestClient

from app import chain, main
from app.report import canonical_json, keccak_hex
from app.schemas import Transaction, WalletSnapshot

ADDR = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"


def fake_snapshot(txs=None, balance=1.5):
    return WalletSnapshot(
        address=ADDR, chain_id=11155111, balance_eth=balance, tx_count=42,
        transactions=txs or [], history_available=True,
    )


@pytest.fixture
def client(monkeypatch):
    async def _build(address):
        chain.normalize_address(address)  # still validate input
        return fake_snapshot()
    monkeypatch.setattr(chain, "build_snapshot", _build)
    # No API key in tests → rules path
    monkeypatch.setattr(main.settings, "anthropic_api_key", "")
    return TestClient(main.app)


def test_health(client):
    body = client.get("/health").json()
    assert body["ok"] is True
    assert body["llm"] == "rules"


def test_rejects_bad_address(client):
    r = client.post("/analyze", json={"address": "not-an-address"})
    assert r.status_code == 400


def test_analyze_returns_hash_matching_report(client):
    r = client.post("/analyze", json={"address": ADDR.lower()})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["snapshot"]["address"] == ADDR  # checksummed
    assert 0 <= body["insight"]["risk_score"] <= 100
    # Hash is reproducible from report_json — this is the on-chain verification story
    assert body["report_hash"] == keccak_hex(body["report_json"])
    assert body["report_hash"].startswith("0x") and len(body["report_hash"]) == 66


def test_rules_flag_approvals_and_failures():
    from app.llm import analyze_with_rules
    txs = [
        Transaction(hash=f"0x{i:064x}", timestamp=1700000000 + i, from_address=ADDR,
                    to_address="0x" + "1" * 40, value_eth=0, is_contract_interaction=True,
                    method="approve", failed=(i < 3))
        for i in range(5)
    ]
    insight = analyze_with_rules(fake_snapshot(txs))
    titles = [f.title for f in insight.flags]
    assert any("failed" in t for t in titles)
    assert any("approval" in t for t in titles)
    assert insight.risk_score > 20


def test_canonical_json_is_order_independent():
    a = canonical_json({"b": 1, "a": [1, 2]})
    b = canonical_json({"a": [1, 2], "b": 1})
    assert a == b == '{"a":[1,2],"b":1}'
