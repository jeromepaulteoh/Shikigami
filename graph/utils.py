import hashlib
import json


def hash_json(data: dict) -> str:
    """SHA-256 hash of deterministically serialized JSON."""
    return hashlib.sha256(
        json.dumps(data, sort_keys=True).encode()
    ).hexdigest()
