import logging

from config import SEED_URL
from clients.tinyfish import TinyFishClient
from graph import init_db, get_meta, set_meta, hash_json

logger = logging.getLogger(__name__)


async def check_canary(db_path: str | None = None) -> dict:
    """Fetch seed page, hash it, compare against stored hash.

    Returns {"status": "stable"|"changed", "should_block": False}.
    Never blocks — only flags changes.
    """
    await init_db(db_path)

    client = TinyFishClient()
    result = await client.run_single(
        url=SEED_URL,
        goal="Return the top-level navigation links on this page as a JSON array of {text, href} objects",
    )

    # On fetch error: flag as changed but don't update stored hash
    if "error" in result:
        logger.warning("Canary fetch failed: %s", result)
        return {"status": "changed", "should_block": False}

    current_hash = hash_json(result)
    stored_hash = await get_meta("canary_hash", db_path)

    if stored_hash is None:
        logger.info("Canary: first run, storing baseline hash")
        status = "stable"
    elif stored_hash == current_hash:
        logger.info("Canary: stable (hash unchanged)")
        status = "stable"
    else:
        logger.warning("Canary: page structure CHANGED (old=%s new=%s)", stored_hash[:12], current_hash[:12])
        print("MAINTENANCE NEEDED")
        status = "changed"

    # Store latest hash (only on successful fetch)
    await set_meta("canary_hash", current_hash, db_path)
    return {"status": status, "should_block": False}
