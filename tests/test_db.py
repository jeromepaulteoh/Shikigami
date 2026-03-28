import asyncio
import json
import os
import sys

# Add project root to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graph import Node, init_db, upsert_node, get_node, get_nodes_by_form_fields, save_version, get_meta, set_meta

TEST_DB = "test_regflow.db"


async def main():
    # Clean slate
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    try:
        # 1. Initialize database
        await init_db(TEST_DB)
        print("[PASS] init_db — tables created")

        # 2. Insert a node
        node = Node(
            url="https://www.mas.gov.sg/regulation/test-page",
            parent_url="https://www.mas.gov.sg/regulation",
            extraction_goal="Find the minimum capital requirement",
            depth_from_seed=1,
            section_type="circular",
            relevant_form_fields=json.dumps(["min_paid_up_capital"]),
        )
        await upsert_node(node, TEST_DB)
        print("[PASS] upsert_node — node inserted")

        # 3. Read it back
        fetched = await get_node("https://www.mas.gov.sg/regulation/test-page", TEST_DB)
        assert fetched is not None, "get_node returned None"
        assert fetched.url == node.url, f"URL mismatch: {fetched.url}"
        assert fetched.extraction_goal == node.extraction_goal, "extraction_goal mismatch"
        assert fetched.depth_from_seed == 1, "depth_from_seed mismatch"
        assert fetched.id is not None, "id should be auto-assigned"
        print(f"[PASS] get_node — retrieved node (id={fetched.id})")

        # 4. Upsert same URL with updated goal (test ON CONFLICT)
        node.extraction_goal = "Updated goal for capital requirement"
        await upsert_node(node, TEST_DB)
        fetched2 = await get_node(node.url, TEST_DB)
        assert fetched2.extraction_goal == "Updated goal for capital requirement", "upsert did not update"
        assert fetched2.id == fetched.id, "upsert should preserve id"
        print("[PASS] upsert_node — conflict update preserves id")

        # 5. Query by form fields
        matches = await get_nodes_by_form_fields(["min_paid_up_capital"], TEST_DB)
        assert len(matches) == 1, f"Expected 1 match, got {len(matches)}"
        assert matches[0].url == node.url
        print("[PASS] get_nodes_by_form_fields — found matching node")

        # 6. Query with non-matching field returns empty
        no_matches = await get_nodes_by_form_fields(["nonexistent_field"], TEST_DB)
        assert len(no_matches) == 0, f"Expected 0 matches, got {len(no_matches)}"
        print("[PASS] get_nodes_by_form_fields — no false positives")

        # 7. Save a version
        await save_version(fetched.id, "abc123hash", '{"value": "250000"}', TEST_DB)
        print("[PASS] save_version — version saved")

        # 8. Set and get meta
        await set_meta("test_key", "test_value", TEST_DB)
        val = await get_meta("test_key", TEST_DB)
        assert val == "test_value", f"Expected 'test_value', got '{val}'"
        print("[PASS] set_meta / get_meta — round trip works")

        # 9. Update meta
        await set_meta("test_key", "updated_value", TEST_DB)
        val2 = await get_meta("test_key", TEST_DB)
        assert val2 == "updated_value", f"Expected 'updated_value', got '{val2}'"
        print("[PASS] set_meta — update works")

        # 10. Get non-existent meta
        missing = await get_meta("no_such_key", TEST_DB)
        assert missing is None, f"Expected None, got '{missing}'"
        print("[PASS] get_meta — returns None for missing key")

        print("\n=== All Phase 1 tests passed ===")

    finally:
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


if __name__ == "__main__":
    asyncio.run(main())
