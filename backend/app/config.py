from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIDA_", env_file=".env", extra="ignore")

    app_name: str = "AI Deepfake Analyzer"
    deployment_mode: str = "local"
    database_url: str = "sqlite:///./.data/app.db"
    data_dir: Path = Path(".data")
    redis_url: str = "redis://localhost:6379/0"
    use_rq: bool = False

    encryption_key: str | None = None
    media_ttl_minutes: int = 15
    job_ttl_hours: int = 24
    max_upload_bytes: int = 15 * 1024 * 1024
    max_image_pixels: int = 36_000_000
    request_timeout_seconds: float = 12.0
    require_access_token: bool = False
    access_token_sha256: str | None = None
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 120
    analysis_rate_limit_max_requests: int = 12
    metrics_enabled: bool = True
    audit_salt: str | None = None

    enable_hf_model: bool = False
    hf_model_id: str = "Ateeqq/ai-vs-human-image-detector"
    hf_model_ids: str = (
        "Ateeqq/ai-vs-human-image-detector,"
        "dima806/ai_vs_real_image_detection,"
        "jacoballessio/ai-image-detect-distilled,"
        "SadraCoding/SDXL-Deepfake-Detector"
    )

    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:4173",
            "http://localhost:4173",
        ]
    )
    allowed_image_types: set[str] = Field(
        default_factory=lambda: {
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/gif",
            "image/bmp",
            "image/tiff",
        }
    )

    @field_validator("encryption_key")
    @classmethod
    def validate_fernet_key(cls, value: str | None) -> str | None:
        if not value:
            return value
        try:
            Fernet(value.encode("utf-8"))
        except Exception as exc:  # pragma: no cover - pydantic surfaces this text.
            raise ValueError("AIDA_ENCRYPTION_KEY must be a valid Fernet key") from exc
        return value

    @field_validator("access_token_sha256")
    @classmethod
    def validate_access_token_hash(cls, value: str | None) -> str | None:
        if not value:
            return value
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("AIDA_ACCESS_TOKEN_SHA256 must be a lowercase SHA-256 hex digest")
        return normalized

    @property
    def is_production(self) -> bool:
        return self.deployment_mode.lower() == "production"

    def production_errors(self) -> list[str]:
        if not self.is_production:
            return []

        errors: list[str] = []
        if not self.encryption_key:
            errors.append("AIDA_ENCRYPTION_KEY is required in production.")
        if self.database_url.startswith("sqlite"):
            errors.append("AIDA_DATABASE_URL must use PostgreSQL or another server database in production.")
        if not self.use_rq:
            errors.append("AIDA_USE_RQ=true is required in production so image analysis runs in workers.")
        local_origins = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:4173", "http://localhost:4173"}
        if not self.allowed_origins or all(origin in local_origins for origin in self.allowed_origins):
            errors.append("AIDA_ALLOWED_ORIGINS must include the deployed frontend origin in production.")
        if self.require_access_token and not self.access_token_sha256:
            errors.append("AIDA_ACCESS_TOKEN_SHA256 is required when access token protection is enabled.")
        if not self.rate_limit_enabled:
            errors.append("AIDA_RATE_LIMIT_ENABLED=true is required in production.")
        if not self.audit_salt:
            errors.append("AIDA_AUDIT_SALT is required in production for privacy-safe audit identifiers.")
        return errors


@lru_cache
def get_settings() -> Settings:
    return Settings()
