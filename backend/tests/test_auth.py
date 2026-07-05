import hashlib

from app.auth import token_matches
from app.config import Settings


def test_access_token_hash_matching() -> None:
    digest = hashlib.sha256("correct-token".encode("utf-8")).hexdigest()
    settings = Settings(require_access_token=True, access_token_sha256=digest)

    assert token_matches("correct-token", settings)
    assert not token_matches("wrong-token", settings)
    assert not token_matches(None, settings)


def test_access_token_disabled_allows_requests() -> None:
    settings = Settings(require_access_token=False)

    assert token_matches(None, settings)
