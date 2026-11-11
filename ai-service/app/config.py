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

    # LLM — resolution order: Anthropic key → Ollama (if enabled) → rules fallback
    anthropic_api_key: str = ""  # optional
    anthropic_model: str = "claude-sonnet-5-5"

    ollama_enabled: bool = False  # free local model via https://ollama.com
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"  # or llama3.2:3b on a lighter machine
    ollama_timeout_s: float = 180.0  # first call loads the model into memory; be patient

    # API
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_transactions: int = 25

    @property
    def llm_label(self) -> str:
        if self.anthropic_api_key:
            return f"claude:{self.anthropic_model}"
        if self.ollama_enabled:
            return f"ollama:{self.ollama_model}"
        return "rules"


settings = Settings()
