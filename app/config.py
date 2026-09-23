from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        extra="ignore",
    )

    verify_token: str = "dev-verify-token"
    meta_app_secret: str = ""
    ig_access_token: str = ""
    ig_user_id: str = ""
    graph_api_version: str = "v25.0"
    graph_base_url: str = "https://graph.instagram.com"
    n8n_webhook_url: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    database_path: str = "data/conversations.db"
    system_prompt_path: str = "prompts/system.txt"
    history_limit: int = 10

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return ROOT / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
