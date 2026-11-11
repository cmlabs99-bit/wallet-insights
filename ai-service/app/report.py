"""Canonical serialization + hashing of a report.

The dashboard sends `report_hash` straight to InsightRegistry.saveInsight. Anyone holding
the report JSON can recompute keccak256(report_json) and compare it to what is on-chain.
Canonical form matters: same data must always produce the same bytes.
"""

import json

from eth_hash.auto import keccak


def canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def keccak_hex(text: str) -> str:
    return "0x" + keccak(text.encode("utf-8")).hex()
