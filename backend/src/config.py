from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parent.parent

DEV_JWT_SECRET = "docqa_default_secret_key_change_in_production"


class Settings(BaseSettings):
    app_env: str = "development"
    gemini_api_key: str = ""
    database_url: str = "postgresql+asyncpg://docqa:docqa_secret@localhost:5433/docqa"
    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440
    chroma_persist_dir: str = str(BACKEND_DIR / "chroma_data")
    upload_dir: str = str(BACKEND_DIR / "uploads")
    llm_model: str = "gemini-3.5-flash"
    embedding_model: str = "gemini-embedding-001"
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 5
    min_relevance_score: float = 0.60
    rate_limit_chat_per_minute: int = 20
    rate_limit_upload_per_minute: int = 10
    rate_limit_auth_per_minute: int = 10
    log_level: str = "INFO"
    max_file_size_mb: int = 20
    allowed_extensions: set[str] = {".pdf", ".txt", ".docx", ".md"}

    @model_validator(mode="after")
    def _reject_insecure_production_config(self) -> "Settings":
        if self.app_env.lower() == "production":
            if self.jwt_secret == DEV_JWT_SECRET:
                raise ValueError(
                    "JWT_SECRET must be set to a unique secret when APP_ENV=production"
                )
            if not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY must be set when APP_ENV=production")
        return self

    model_config = {
        "env_file": [".env", "../.env"],
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
