"""
All configuration loaded from environment variables.
Uses pydantic-settings for validation and type safety.
"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Anthropic ────────────────────────────────────────
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    anthropic_model: str = Field("claude-sonnet-4-20250514")

    # ── Polymarket ───────────────────────────────────────
    poly_private_key: str = Field(default="", description="Polygon wallet private key")
    poly_api_key: str = Field(default="")
    poly_api_secret: str = Field(default="")
    poly_api_passphrase: str = Field(default="")
    poly_gamma_url: str = Field("https://gamma-api.polymarket.com")
    poly_clob_url: str = Field("https://clob.polymarket.com")

    # ── Kalshi ───────────────────────────────────────────
    kalshi_api_key: str = Field(default="")
    kalshi_base_url: str = Field("https://trading-api.kalshi.com/trade-api/v2")

    # ── Telegram ─────────────────────────────────────────
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")

    # ── Trading mode ─────────────────────────────────────
    live_mode: bool = Field(False, description="NEVER set true without paper validation")
    dry_run_log_path: str = Field("./storage/paper_trades.jsonl")

    # ── Risk ─────────────────────────────────────────────
    max_stake_per_market_usd: float = Field(10.0)
    max_total_exposure_usd: float = Field(100.0)
    min_edge_threshold: float = Field(0.05)
    max_resolve_days: int = Field(5)
    kelly_fraction: float = Field(0.25)

    # ── Free data sources ────────────────────────────────
    gdelt_api_url: str = Field("https://api.gdeltproject.org/api/v2/doc/doc")
    reddit_client_id: str = Field(default="")
    reddit_client_secret: str = Field(default="")
    reddit_user_agent: str = Field("polymarket-agent/1.0")

    # ── Storage ──────────────────────────────────────────
    sqlite_path: str = Field("./storage/agent.db")
    chroma_path: str = Field("./storage/chroma_db")

    # ── Cycle ────────────────────────────────────────────
    cycle_interval_seconds: int = Field(900)


@lru_cache
def get_settings() -> Settings:
    """Singleton settings — loaded once, reused everywhere."""
    return Settings()
