from __future__ import annotations

import hmac
import hashlib


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    cleaned = signature.removeprefix("sha256=")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, cleaned)
