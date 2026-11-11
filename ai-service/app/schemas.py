from typing import Literal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    hash: str
    timestamp: int
    from_address: str
    to_address: str | None  # None for contract creation
    value_eth: float
    is_contract_interaction: bool
    method: str | None = None  # decoded function name if Etherscan knows it, else selector
    failed: bool = False
    gas_used: int = 0


class WalletSnapshot(BaseModel):
    address: str
    chain_id: int
    balance_eth: float
    tx_count: int
    transactions: list[Transaction]
    history_available: bool = True
    note: str | None = None


class RiskFlag(BaseModel):
    severity: Literal["low", "medium", "high"]
    title: str
    detail: str
    tx_hash: str | None = None


class WalletInsight(BaseModel):
    summary: str = Field(description="2-3 plain-English sentences about this wallet")
    activity_overview: str = Field(description="What the wallet has been doing recently")
    risk_score: int = Field(ge=0, le=100, description="0 = nothing concerning, 100 = act now")
    flags: list[RiskFlag] = []
    suggestions: list[str] = []
    generated_by: str = "rules"  # "claude:<model>" or "rules"


class AnalyzeRequest(BaseModel):
    address: str


class AnalyzeResponse(BaseModel):
    snapshot: WalletSnapshot
    insight: WalletInsight
    report_json: str  # canonical JSON of the insight — this is what gets hashed
    report_hash: str  # 0x-prefixed keccak256 of report_json; pass straight to the contract
