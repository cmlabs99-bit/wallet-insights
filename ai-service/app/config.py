from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The whole monorepo shares one .env at the repo root.
ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")

    # Chain
    chain_id: int = 11155111  # Sepolia
    rpc_url: str = "https://rpc.sepolia.org"
    etherscan_api_key: str = ""  # optional; without it we skip transaction history

    # LLM
    anthropic_api_key: str = ""  # optional; without it the service uses a rule-based fallback
    anthropic_model: str = "claude-sonnet-5-5"

    # API
    cors_origins: str = "http://localhost:5173"
    max_transactions: int = 25


settings = Settings()
