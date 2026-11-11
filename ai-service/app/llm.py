"""Turn a WalletSnapshot into a WalletInsight.

Three paths, tried in this order (see Settings.llm_label):
  * analyze_with_claude — Anthropic API. Uses tool-use so the model fills a typed schema
    and we never parse free text.
  * analyze_with_ollama — a free local model via Ollama. Same prompt and the same JSON
    schema, enforced through Ollama's `format` parameter.
  * analyze_with_rules — a small deterministic fallback so the whole app runs end to end
    with no model at all (and so tests are fast and offline).
"""

from __future__ import annotations

import json

import httpx
from anthropic import AsyncAnthropic

from .config import settings
from .schemas import RiskFlag, WalletInsight, WalletSnapshot

SYSTEM_PROMPT = """You are an on-chain analyst explaining an Ethereum wallet to its owner.
You get a snapshot: balance, transaction count, and recent transactions (newest first).
Write for a smart non-expert. Be concrete: refer to specific transactions by their first
10 characters of hash when you flag them. Do not invent transactions that are not in the
snapshot. If history is unavailable, say so plainly and base the summary on what you have.

Risk scoring guide (0-100):
  0-20  ordinary activity, nothing to act on
 21-50  something worth a look (repeated failed txs, many unknown contracts, dust)
 51-80  likely problem (approvals to unverified contracts, drained balance pattern)
 81-100 act now (clear drainer/phishing pattern)
Only flag what the data supports. Suggestions must be actions the owner can take.

Facts you must respect:
- All amounts are in ETH. Never write a dollar sign or convert to USD.
- Chain IDs: 1 = Ethereum mainnet, 11155111 = Sepolia testnet, 31337 = local Hardhat
  development chain (test ETH, not real money). Name the chain correctly.
- If recent_transactions is empty and history_available is false, do not raise flags
  about missing transactions — say history was not fetched and score risk 0-10.
- Keep summary to 2-3 sentences and activity_overview to 1-2. Do not repeat yourself.

"""

# One JSON schema shared by both model paths; mirrors WalletInsight minus generated_by.
# tx_hash is a plain string (empty when not applicable) because some local models
# reject union types like ["string", "null"].
INSIGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "activity_overview": {"type": "string"},
        "risk_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "tx_hash": {"type": "string"},
                },
                "required": ["severity", "title", "detail"],
            },
        },
        "suggestions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "activity_overview", "risk_score", "flags", "suggestions"],
}

INSIGHT_TOOL = {
    "name": "report_insight",
    "description": "Report the analysis of the wallet snapshot.",
    "input_schema": INSIGHT_SCHEMA,
}


def _snapshot_for_prompt(snapshot: WalletSnapshot) -> str:
    # Keep the prompt compact: the model doesn't need every field.
    txs = [
        {
            "hash": t.hash,
            "when": t.timestamp,
            "direction": "out" if t.from_address.lower() == snapshot.address.lower() else "in",
            "counterparty": t.to_address if t.from_address.lower() == snapshot.address.lower() else t.from_address,
            "value_eth": round(t.value_eth, 6),
            "contract_call": t.is_contract_interaction,
            "method": t.method,
            "failed": t.failed,
        }
        for t in snapshot.transactions
    ]
    return json.dumps(
        {
            "address": snapshot.address,
            "chain_id": snapshot.chain_id,
            "balance_eth": round(snapshot.balance_eth, 6),
            "lifetime_tx_count": snapshot.tx_count,
            "history_available": snapshot.history_available,
            "note": snapshot.note,
            "recent_transactions": txs,
        },
        indent=1,
    )


def _finish(data: dict, generated_by: str) -> WalletInsight:
    """Normalise model output into a WalletInsight."""
    for flag in data.get("flags", []):
        if not flag.get("tx_hash"):
            flag["tx_hash"] = None  # schema says string; model may send "" — treat as absent
    data["generated_by"] = generated_by
    return WalletInsight.model_validate(data)


async def analyze_with_claude(snapshot: WalletSnapshot) -> WalletInsight:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        tools=[INSIGHT_TOOL],
        tool_choice={"type": "tool", "name": "report_insight"},
        messages=[{"role": "user", "content": f"Wallet snapshot:\n{_snapshot_for_prompt(snapshot)}"}],
    )
    tool_use = next(b for b in msg.content if b.type == "tool_use")
    return _finish(dict(tool_use.input), f"claude:{settings.anthropic_model}")


async def analyze_with_ollama(snapshot: WalletSnapshot) -> WalletInsight:
    """Same prompt and schema as the Claude path, served by a local Ollama model.

    Ollama's `format` parameter accepts a JSON schema and constrains generation to it,
    so the reply's `content` is a JSON string we can parse directly.
    """
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "format": INSIGHT_SCHEMA,
        "options": {"temperature": 0.2},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Wallet snapshot:\n{_snapshot_for_prompt(snapshot)}"},
        ],
    }
    async with httpx.AsyncClient(timeout=settings.ollama_timeout_s) as client:
        try:
            r = await client.post(f"{settings.ollama_url}/api/chat", json=payload)
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Could not reach Ollama at {settings.ollama_url}. Is the Ollama app running? "
                f"(install from https://ollama.com, then `ollama pull {settings.ollama_model}`)"
            ) from e
        if r.status_code == 404:
            raise RuntimeError(
                f"Ollama has no model named '{settings.ollama_model}'. Run: ollama pull {settings.ollama_model}"
            )
        r.raise_for_status()
    content = r.json()["message"]["content"]
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Ollama returned non-JSON output: {content[:200]}") from e
    return _finish(data, f"ollama:{settings.ollama_model}")


def analyze_with_rules(snapshot: WalletSnapshot) -> WalletInsight:
    """Cheap heuristics. Good enough to demo the UI and to test the plumbing."""
    txs = snapshot.transactions
    flags: list[RiskFlag] = []
    score = 5

    failed = [t for t in txs if t.failed]
    if len(failed) >= 3:
        score += 15
        flags.append(RiskFlag(
            severity="medium",
            title=f"{len(failed)} failed transactions recently",
            detail="Repeated failures often mean a bad contract call, insufficient gas, or a front-run swap.",
            tx_hash=failed[0].hash,
        ))

    approvals = [t for t in txs if (t.method or "").lower() in {"approve", "setapprovalforall"}]
    if approvals:
        score += 10 * min(len(approvals), 3)
        flags.append(RiskFlag(
            severity="medium" if len(approvals) < 3 else "high",
            title=f"{len(approvals)} token approval(s)",
            detail="Approvals let a contract move your tokens later. Review and revoke any you don't recognise.",
            tx_hash=approvals[0].hash,
        ))

    outgoing = [t for t in txs if t.from_address.lower() == snapshot.address.lower() and t.value_eth > 0]
    if outgoing and snapshot.balance_eth < 0.001 and sum(t.value_eth for t in outgoing) > 0.05:
        score += 30
        flags.append(RiskFlag(
            severity="high",
            title="Balance is near zero after outgoing transfers",
            detail="This can be normal (you moved funds) or a drain. Confirm you recognise the recipients.",
            tx_hash=outgoing[0].hash,
        ))

    contract_calls = sum(1 for t in txs if t.is_contract_interaction)
    if not snapshot.history_available:
        overview = "Transaction history is not available in this environment, so this is based on balance only."
    elif not txs:
        overview = "No transactions found. This looks like a fresh or dormant wallet."
    else:
        overview = (
            f"{len(txs)} recent transactions: {contract_calls} contract interactions, "
            f"{len(outgoing)} outgoing ETH transfers, {len(failed)} failed."
        )

    suggestions = ["Set ANTHROPIC_API_KEY or OLLAMA_ENABLED=true in .env for a narrative analysis."]
    if approvals:
        suggestions.append("Check your approvals at revoke.cash and revoke stale ones.")
    if snapshot.balance_eth < 0.01:
        suggestions.append("Keep a small ETH buffer so you can always pay gas for a revoke or exit.")

    return WalletInsight(
        summary=(
            f"Wallet {snapshot.address[:6]}…{snapshot.address[-4:]} holds {snapshot.balance_eth:.4f} ETH "
            f"with {snapshot.tx_count} lifetime transactions."
        ),
        activity_overview=overview,
        risk_score=min(score, 100),
        flags=flags,
        suggestions=suggestions,
        generated_by="rules",
    )


async def analyze(snapshot: WalletSnapshot) -> WalletInsight:
    if settings.anthropic_api_key:
        return await analyze_with_claude(snapshot)
    if settings.ollama_enabled:
        return await analyze_with_ollama(snapshot)
    return analyze_with_rules(snapshot)
