"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Telegram
    telegram_token: str = Field(..., description="Telegram Bot API token")
    allowed_chat_ids: list[int] = Field(default_factory=list)
    maintainer_chat_id: int = Field(default=0, description="Chat ID for dev notifications")

    # AI
    ai_command: str = Field(default="claude", alias="AI_COMMAND")
    claude_command: str = Field(default="")  # Deprecated, use ai_command
    session_timeout_hours: int = Field(default=24)

    @property
    def effective_ai_command(self) -> str:
        return self.ai_command or self.claude_command or "claude"
    
    # Authentication
    require_auth: bool = Field(default=True)
    auth_secret_key: str = Field(default="")
    auth_timeout_minutes: int = Field(default=30)
    
    # Paths
    base_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    
    @field_validator("auth_secret_key", mode="after")
    @classmethod
    def validate_auth_secret_key(cls, v, info):
        """REQUIRE_AUTH=true일 때 빈 AUTH_SECRET_KEY 방지."""
        # info.data에서 require_auth 값 확인
        require_auth = info.data.get("require_auth", True)
        if require_auth and not v:
            raise ValueError(
                "AUTH_SECRET_KEY is required when REQUIRE_AUTH=true. "
                "Set AUTH_SECRET_KEY in .env or set REQUIRE_AUTH=false."
            )
        return v

    @field_validator("allowed_chat_ids", mode="before")
    @classmethod
    def parse_chat_ids(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        if isinstance(v, list):
            return v
        return []
    
    @property
    def data_dir(self) -> Path:
        return self.base_dir / ".data"
    
    @property
    def sessions_file(self) -> Path:
        return self.data_dir / "sessions.json"
    
    @property
    def prompts_dir(self) -> Path:
        return self.base_dir / "prompts"
    
    @property
    def telegram_prompt_file(self) -> Path:
        return self.prompts_dir / "telegram.md"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
