from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from .config import Settings, get_settings

logger = logging.getLogger("aida.audit")


def privacy_hash(value: str | None, settings: Settings | None = None) -> str | None:
    if not value:
        return None
    settings = settings or get_settings()
    salt = settings.audit_salt or settings.encryption_key or "local-dev-audit-salt"
    return hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()[:16]


def audit_event(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        **{key: value for key, value in fields.items() if value is not None},
    }
    logger.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))
