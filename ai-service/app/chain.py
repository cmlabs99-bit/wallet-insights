"""Read-only chain access: balance via JSON-RPC, transaction history via Etherscan.

Nothing here signs anything. The service never holds a private key.
"""

import httpx
from eth_utils import is_address, to_checksum_address

from .config import settings
from .schemas import Transaction, WalletSnapshot

ETHERSCAN_V2 = "https://api.etherscan.io/v2/api"


def normalize_address(address: str) -> str:
    if not is_address(address):
        raise ValueError(f"'{address}' is not a valid Ethereum address")
    return to_checksum_address(address)


async def get_balance_eth(client: httpx.AsyncClient, address: str) -> float:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance", "params": [address, "latest"]}
    r = await client.post(settings.rpc_url, json=payload, timeout=15)
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise RuntimeError(f"RPC error: {body['error']}")
    return int(body["result"], 16) / 1e18


async def get_tx_count(client: httpx.AsyncClient, address: str) -> int:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionCount", "params": [address, "latest"]}
    r = await client.post(settings.rpc_url, json=payload, timeout=15)
    r.raise_for_status()
    return int(r.json()["result"], 16)


def _parse_tx(raw: dict) -> Transaction:
    inp = raw.get("input") or "0x"
    method = raw.get("functionName") or None
    if method:
        method = method.split("(")[0]  # "transfer(address,uint256)" -> "transfer"
    elif inp != "0x" and len(inp) >= 10:
        method = inp[:10]  # 4-byte selector
    return Transaction(
        hash=raw["hash"],
        timestamp=int(raw["timeStamp"]),
        from_address=to_checksum_address(raw["from"]),
        to_address=to_checksum_address(raw["to"]) if raw.get("to") else None,
        value_eth=int(raw["value"]) / 1e18,
        is_contract_interaction=inp != "0x",
        method=method,
        failed=raw.get("isError") == "1",
        gas_used=int(raw.get("gasUsed") or 0),
    )


async def get_transactions(client: httpx.AsyncClient, address: str, limit: int) -> list[Transaction]:
    params = {
        "chainid": settings.chain_id,
        "module": "account",
        "action": "txlist",
        "address": address,
        "sort": "desc",
        "page": 1,
        "offset": limit,
        "apikey": settings.etherscan_api_key,
    }
    r = await client.get(ETHERSCAN_V2, params=params, timeout=20)
    r.raise_for_status()
    body = r.json()
    # Etherscan returns status "0" with message "No transactions found" for empty wallets
    if body.get("status") != "1":
        if "No transactions" in str(body.get("message", "")) or body.get("result") == []:
            return []
        raise RuntimeError(f"Etherscan error: {body.get('message')} {body.get('result')}")
    return [_parse_tx(t) for t in body["result"]]


async def build_snapshot(address: str) -> WalletSnapshot:
    address = normalize_address(address)
    async with httpx.AsyncClient() as client:
        balance = await get_balance_eth(client, address)
        tx_count = await get_tx_count(client, address)
        if settings.etherscan_api_key:
            txs = await get_transactions(client, address, settings.max_transactions)
            history_available, note = True, None
        else:
            txs, history_available = [], False
            note = "Set ETHERSCAN_API_KEY in .env to include transaction history."
    return WalletSnapshot(
        address=address,
        chain_id=settings.chain_id,
        balance_eth=balance,
        tx_count=tx_count,
        transactions=txs,
        history_available=history_available,
        note=note,
    )
