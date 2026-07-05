import hashlib

from cryptography.fernet import Fernet

from app.config import Settings


def test_local_mode_allows_lightweight_defaults() -> None:
    settings = Settings()

    assert settings.production_errors() == []


def test_production_mode_requires_durable_infrastructure() -> None:
    settings = Settings(deployment_mode="production")

    errors = " ".join(settings.production_errors())
    assert "AIDA_ENCRYPTION_KEY" in errors
    assert "AIDA_DATABASE_URL" in errors
    assert "AIDA_USE_RQ=true" in errors
    assert "AIDA_ALLOWED_ORIGINS" in errors
    assert "AIDA_RATE_LIMIT_ENABLED=true" not in errors
    assert "AIDA_AUDIT_SALT" in errors


def test_production_mode_accepts_required_settings() -> None:
    access_token_hash = hashlib.sha256("test-access-token".encode("utf-8")).hexdigest()
    settings = Settings(
        deployment_mode="production",
        encryption_key=Fernet.generate_key().decode(),
        database_url="postgresql+psycopg://aida:secret@postgres:5432/aida",
        use_rq=True,
        allowed_origins=["https://example.org"],
        require_access_token=True,
        access_token_sha256=access_token_hash,
        audit_salt="deployment-specific-random-salt",
    )

    assert settings.production_errors() == []


def test_production_private_beta_requires_token_hash_when_enabled() -> None:
    settings = Settings(
        deployment_mode="production",
        encryption_key=Fernet.generate_key().decode(),
        database_url="postgresql+psycopg://aida:secret@postgres:5432/aida",
        use_rq=True,
        allowed_origins=["https://example.org"],
        require_access_token=True,
        audit_salt="deployment-specific-random-salt",
    )

    assert "AIDA_ACCESS_TOKEN_SHA256" in " ".join(settings.production_errors())
