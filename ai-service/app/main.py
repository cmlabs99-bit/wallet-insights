from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import chain, llm
from .config import settings
from .report import canonical_json, keccak_hex
from .schemas import AnalyzeRequest, AnalyzeResponse, WalletSnapshot

app = FastAPI(title="Wallet Insights AI service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "chain_id": settings.chain_id,
        "llm": settings.llm_label,
        "history": bool(settings.etherscan_api_key),
    }


@app.get("/wallet/{address}/snapshot", response_model=WalletSnapshot)
async def snapshot(address: str):
    try:
        return await chain.build_snapshot(address)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # RPC / Etherscan trouble
        raise HTTPException(status_code=502, detail=f"Chain lookup failed: {e}")


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    snap = await snapshot(req.address)
    try:
        insight = await llm.analyze(snap)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Analysis failed: {e}")

    report_json = canonical_json(insight.model_dump())
    return AnalyzeResponse(
        snapshot=snap,
        insight=insight,
        report_json=report_json,
        report_hash=keccak_hex(report_json),
    )
