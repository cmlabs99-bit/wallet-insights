"""Turn a WalletSnapshot into a WalletInsight.

Two paths:
  * analyze_with_claude — the real thing. Uses Claude's tool-use so the model fills a
    typed schema and we never parse free text.
  * analyze_with_rules — a small deterministic fallback so the whole app runs end to end
    with no API key (and so tests are fast and offline).
"""

from __future__ import annotations

import json

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
Only flag what the data supports. Suggestions must be actions the owner can take."""

# Claude fills this schema via tool-use; it mirrors WalletInsight minus generated_by.
INSIGHT_TOOL = {
    "name": "report_insight",
    "description": "Report the analysis of the wallet snapshot.",
    "input_schema": {
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
                        "tx_hash": {"type": ["string", "null"]},
                    },
                    "required": ["severity", "title", "detail"],
                },
            },
            "suggestions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "activity_overview", "risk_score", "flags", "suggestions"],
    },
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
    data = dict(tool_use.input)
    data["generated_by"] = f"claude:{settings.anthropic_model}"
    return WalletInsight.model_validate(data)


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

    suggestions = ["Connect an LLM key (ANTHROPIC_API_KEY) for a narrative analysis."]
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
    return analyze_with_rules(snapshot)
