import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graph import Node, init_db, upsert_node, get_node, hash_json
from clients.tinyfish import TinyFishClient
from layers.layer2_extract import ExtractionResult, repair_404

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

TEST_DB = "test_regflow.db"

MOCK_REPAIR_RESPONSE = {"new_url": "https://example.com/page-a-moved", "content": {"val": "repaired"}}
MOCK_REEXTRACT_RESPONSE = {"val": "repaired_data", "source": "new_page"}


async def main():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    original_run_single = TinyFishClient.run_single

    try:
        await init_db(TEST_DB)

        # Setup: node with parent_url (repairable)
        node_a = Node(
            url="https://example.com/page-a",
            parent_url="https://example.com/parent",
            extraction_goal="Find value A",
            depth_from_seed=1,
            relevant_form_fields=json.dumps(["field_a"]),
            content_hash="old_hash",
        )
        await upsert_node(node_a, TEST_DB)

        # Setup: node without parent_url (not repairable)
        node_b = Node(
            url="https://example.com/page-b",
            parent_url=None,
            extraction_goal="Find value B",
            depth_from_seed=0,
            relevant_form_fields=json.dumps(["field_b"]),
        )
        await upsert_node(node_b, TEST_DB)

        er_a = ExtractionResult(
            node=node_a, current_json={}, current_hash="",
            status="error_other", prior_hash="old_hash",
        )
        er_b = ExtractionResult(
            node=node_b, current_json={}, current_hash="",
            status="error_other", prior_hash=None,
        )

        # Test 1: Successful repair
        print("\n--- Test 1: successful repair ---")
        call_log = []

        async def mock_run_single(self, url, goal, browser_profile="stealth"):
            call_log.append(url)
            if url == "https://example.com/parent":
                return MOCK_REPAIR_RESPONSE
            elif url == "https://example.com/page-a-moved":
                return MOCK_REEXTRACT_RESPONSE
            return {"error": "failed", "url": url}

        TinyFishClient.run_single = mock_run_single

        results = await repair_404([er_a], TEST_DB)
        assert len(results) == 1
        r = results[0]
        assert r.status == "changed", f"Expected changed, got {r.status}"
        assert r.current_json == MOCK_REEXTRACT_RESPONSE
        assert r.node.url == "https://example.com/page-a-moved"
        print(f"[PASS] repaired — status={r.status}, new_url={r.node.url}")

        # Verify DB was updated
        db_node = await get_node("https://example.com/page-a-moved", TEST_DB)
        assert db_node is not None, "New URL not in DB"
        assert db_node.content_hash == hash_json(MOCK_REEXTRACT_RESPONSE)
        old_node = await get_node("https://example.com/page-a", TEST_DB)
        assert old_node is None, "Old URL should no longer exist"
        print("[PASS] DB updated — old URL removed, new URL stored with hash")

        # Test 2: No parent_url — skip repair
        print("\n--- Test 2: no parent_url (skip) ---")
        results = await repair_404([er_b], TEST_DB)
        assert len(results) == 1
        assert results[0].status == "error_other", "Should remain error"
        assert results[0].node.url == "https://example.com/page-b"
        print("[PASS] no parent — skipped, original error preserved")

        # Test 3: Repair call fails — original error preserved
        print("\n--- Test 3: repair call fails ---")
        node_c = Node(
            url="https://example.com/page-c",
            parent_url="https://example.com/parent",
            extraction_goal="Find value C",
            depth_from_seed=1,
            relevant_form_fields=json.dumps(["field_c"]),
        )
        await upsert_node(node_c, TEST_DB)
        er_c = ExtractionResult(
            node=node_c, current_json={}, current_hash="",
            status="error_other", prior_hash=None,
        )

        async def mock_fail(self, url, goal, browser_profile="stealth"):
            return {"error": "failed", "url": url}

        TinyFishClient.run_single = mock_fail
        results = await repair_404([er_c], TEST_DB)
        assert results[0].status == "error_other"
        print("[PASS] repair failed — original error preserved")

        # Test 4: No valid new_url in response
        print("\n--- Test 4: no new_url in repair response ---")
        node_d = Node(
            url="https://example.com/page-d",
            parent_url="https://example.com/parent",
            extraction_goal="Find value D",
            depth_from_seed=1,
        )
        await upsert_node(node_d, TEST_DB)
        er_d = ExtractionResult(
            node=node_d, current_json={}, current_hash="",
            status="error_other", prior_hash=None,
        )

        async def mock_no_url(self, url, goal, browser_profile="stealth"):
            return {"content": "some data but no new_url key"}

        TinyFishClient.run_single = mock_no_url
        results = await repair_404([er_d], TEST_DB)
        assert results[0].status == "error_other"
        print("[PASS] no new_url — original error preserved")

        # Test 5: Empty list
        print("\n--- Test 5: empty list ---")
        results = await repair_404([], TEST_DB)
        assert results == []
        print("[PASS] empty list returns []")

        print("\n=== All Phase 9 tests passed ===")

    finally:
        TinyFishClient.run_single = original_run_single
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


if __name__ == "__main__":
    asyncio.run(main())
