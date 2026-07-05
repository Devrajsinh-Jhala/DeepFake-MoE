from __future__ import annotations

import hashlib
import hmac

from fastapi import Header, HTTPException, Request, status

from .config import Settings, get_settings

ACCESS_HEADER = "X-AIDA-Access-Token"
ACCESS_COOKIE = "aida_access_token"


def token_matches(token: str | None, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if not settings.require_access_token:
        return True
    if not token or not settings.access_token_sha256:
        return False
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, settings.access_token_sha256)


def require_access(
    request: Request,
    x_aida_access_token: str | None = Header(default=None),
) -> None:
    settings = get_settings()
    token = x_aida_access_token or request.cookies.get(ACCESS_COOKIE)
    if not token_matches(token, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid access token is required.",
            headers={"WWW-Authenticate": ACCESS_HEADER},
        )
