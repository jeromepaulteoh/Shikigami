import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graph import init_db, get_meta, set_meta, hash_json
from clients.tinyfish import TinyFishClient
from layers.layer1_canary import check_canary

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

TEST_DB = "test_regflow.db"
MOCK_NAV = {"links": [{"text": "Regulation", "href": "/regulation"}, {"text": "Licensing", "href": "/licensing"}]}


async def main():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    # Save original method for restoration
    original_run_single = TinyFishClient.run_single

    try:
        await init_db(TEST_DB)

        # Mock TinyFishClient.run_single to return fixed data
        async def mock_run_single(self, url, goal, browser_profile="stealth"):
            return MOCK_NAV

        TinyFishClient.run_single = mock_run_single

        # Test 1: First run — no stored hash, should return stable
        print("\n--- Test 1: first run (no stored hash) ---")
        result = await check_canary(TEST_DB)
        assert result["status"] == "stable", f"Expected stable, got {result['status']}"
        assert result["should_block"] is False
        stored = await get_meta("canary_hash", TEST_DB)
        assert stored == hash_json(MOCK_NAV), "Hash not stored after first run"
        print(f"[PASS] first run — stable, hash stored: {stored[:16]}...")

        # Test 2: Same hash — should return stable
        print("\n--- Test 2: same hash (unchanged) ---")
        result = await check_canary(TEST_DB)
        assert result["status"] == "stable", f"Expected stable, got {result['status']}"
        assert result["should_block"] is False
        print("[PASS] unchanged — stable")

        # Test 3: Different hash — should return changed
        print("\n--- Test 3: different hash (changed) ---")
        await set_meta("canary_hash", "old_hash_that_wont_match", TEST_DB)
        result = await check_canary(TEST_DB)
        assert result["status"] == "changed", f"Expected changed, got {result['status']}"
        assert result["should_block"] is False
        new_stored = await get_meta("canary_hash", TEST_DB)
        assert new_stored == hash_json(MOCK_NAV), "Hash should be updated to new value"
        print("[PASS] changed — flagged, hash updated")

        # Test 4: TinyFish error — should return changed, NOT update hash
        print("\n--- Test 4: fetch error ---")
        await set_meta("canary_hash", "preserved_hash", TEST_DB)

        async def mock_error(self, url, goal, browser_profile="stealth"):
            return {"error": "failed", "url": url}

        TinyFishClient.run_single = mock_error
        result = await check_canary(TEST_DB)
        assert result["status"] == "changed", f"Expected changed on error, got {result['status']}"
        assert result["should_block"] is False
        preserved = await get_meta("canary_hash", TEST_DB)
        assert preserved == "preserved_hash", f"Hash should NOT be updated on error, got {preserved}"
        print("[PASS] error — flagged as changed, hash preserved")

        # Test 5: should_block is always False
        print("\n--- Test 5: should_block always False ---")
        # Already verified in all tests above
        print("[PASS] should_block is False in all scenarios")

        print("\n=== All Phase 4 tests passed ===")

    finally:
        TinyFishClient.run_single = original_run_single
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


if __name__ == "__main__":
    asyncio.run(main())
