import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graph import Node, init_db, upsert_node, get_node, hash_json
from clients.tinyfish import TinyFishClient
from layers.layer2_extract import parallel_extract
import aiosqlite

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

TEST_DB = "test_regflow.db"

MOCK_RESULT_A = {"value": "250000", "currency": "SGD"}
MOCK_RESULT_B = {"value": "20000", "currency": "SGD"}
MOCK_ERROR = {"error": "failed", "url": "https://example.com/broken"}


async def main():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    original_run_batch = TinyFishClient.run_batch

    try:
        await init_db(TEST_DB)

        # Insert test nodes
        node_a = Node(
            url="https://example.com/page-a",
            extraction_goal="Extract value A",
            depth_from_seed=1,
            relevant_form_fields=json.dumps(["field_a"]),
        )
        node_b = Node(
            url="https://example.com/page-b",
            extraction_goal="Extract value B",
            depth_from_seed=1,
            relevant_form_fields=json.dumps(["field_b"]),
            content_hash=hash_json(MOCK_RESULT_B),  # pre-set to match mock
        )
        node_err = Node(
            url="https://example.com/broken",
            extraction_goal="Extract broken",
            depth_from_seed=1,
            relevant_form_fields=json.dumps(["field_err"]),
            content_hash="preserved_hash",
        )
        await upsert_node(node_a, TEST_DB)
        await upsert_node(node_b, TEST_DB)
        await upsert_node(node_err, TEST_DB)

        # Mock run_batch: return results matching node order
        async def mock_run_batch(self, tasks):
            results = []
            for t in tasks:
                if "broken" in t["url"]:
                    results.append({"error": "failed", "url": t["url"]})
                elif "page-a" in t["url"]:
                    results.append(MOCK_RESULT_A)
                elif "page-b" in t["url"]:
                    results.append(MOCK_RESULT_B)
            return results

        TinyFishClient.run_batch = mock_run_batch

        # Re-fetch nodes from DB to get IDs
        node_a = await get_node("https://example.com/page-a", TEST_DB)
        node_b = await get_node("https://example.com/page-b", TEST_DB)
        node_err = await get_node("https://example.com/broken", TEST_DB)

        # Test 1: Empty list
        print("\n--- Test 1: empty node list ---")
        results = await parallel_extract([], TEST_DB)
        assert results == [], f"Expected empty list, got {results}"
        print("[PASS] empty list returns []")

        # Test 2: Mixed batch (changed, unchanged, error)
        print("\n--- Test 2: mixed batch ---")
        results = await parallel_extract([node_a, node_b, node_err], TEST_DB)
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"

        r_a, r_b, r_err = results

        # node_a: no prior hash → changed
        assert r_a.status == "changed", f"Expected changed, got {r_a.status}"
        assert r_a.prior_hash is None, f"Expected None prior_hash, got {r_a.prior_hash}"
        assert r_a.current_json == MOCK_RESULT_A
        assert r_a.current_hash == hash_json(MOCK_RESULT_A)
        print(f"[PASS] node_a — changed (first extraction), hash={r_a.current_hash[:16]}...")

        # node_b: matching hash → unchanged
        assert r_b.status == "unchanged", f"Expected unchanged, got {r_b.status}"
        assert r_b.prior_hash == hash_json(MOCK_RESULT_B)
        assert r_b.current_hash == r_b.prior_hash
        print(f"[PASS] node_b — unchanged")

        # node_err: error
        assert r_err.status == "error_other", f"Expected error_other, got {r_err.status}"
        assert r_err.current_json == {}
        assert r_err.current_hash == ""
        print(f"[PASS] node_err — error_other")

        # Test 3: DB updated for successful nodes
        print("\n--- Test 3: DB updates ---")
        db_a = await get_node("https://example.com/page-a", TEST_DB)
        assert db_a.content_hash == hash_json(MOCK_RESULT_A), "node_a hash not updated in DB"
        assert db_a.last_extracted_json is not None, "node_a last_extracted_json not set"
        assert db_a.last_extracted_at is not None, "node_a last_extracted_at not set"
        print("[PASS] node_a DB updated (hash, json, timestamp)")

        db_b = await get_node("https://example.com/page-b", TEST_DB)
        assert db_b.last_extracted_at is not None, "node_b last_extracted_at not set"
        print("[PASS] node_b DB updated (timestamp refreshed)")

        # Test 4: Error node — hash preserved, timestamp updated
        print("\n--- Test 4: error node DB state ---")
        db_err = await get_node("https://example.com/broken", TEST_DB)
        assert db_err.content_hash == "preserved_hash", f"Error node hash should be preserved, got {db_err.content_hash}"
        assert db_err.last_extracted_at is not None, "Error node last_extracted_at not set"
        print("[PASS] error node — hash preserved, timestamp updated")

        # Test 5: save_version called for successes
        print("\n--- Test 5: version history ---")
        async with aiosqlite.connect(TEST_DB) as db:
            async with db.execute("SELECT COUNT(*) FROM node_versions") as c:
                count = (await c.fetchone())[0]
            assert count == 2, f"Expected 2 versions (a + b), got {count}"
        print("[PASS] 2 versions saved (successes only, not errors)")

        print("\n=== All Phase 5 tests passed ===")

    finally:
        TinyFishClient.run_batch = original_run_batch
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


if __name__ == "__main__":
    asyncio.run(main())
