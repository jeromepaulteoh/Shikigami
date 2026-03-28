import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graph import Node, init_db, upsert_node, get_node, save_version, hash_json
from layers.layer2_extract import ExtractionResult
import layers.layer3_diff as diff_module
from layers.layer3_diff import semantic_diff, DiffResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

TEST_DB = "test_regflow.db"

PRIOR_DATA = {"value": "250000", "currency": "SGD"}
CURRENT_DATA = {"value": "500000", "currency": "SGD"}


async def main():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    original_chat_json = diff_module.chat_json

    try:
        await init_db(TEST_DB)

        # Setup: insert a node and two versions (prior + current)
        node = Node(
            url="https://example.com/capital",
            extraction_goal="Find minimum capital",
            depth_from_seed=1,
            relevant_form_fields=json.dumps(["min_paid_up_capital"]),
            content_hash=hash_json(CURRENT_DATA),
        )
        await upsert_node(node, TEST_DB)
        db_node = await get_node(node.url, TEST_DB)

        # Save prior version, then current version
        await save_version(db_node.id, hash_json(PRIOR_DATA), json.dumps(PRIOR_DATA, sort_keys=True), TEST_DB)
        await save_version(db_node.id, hash_json(CURRENT_DATA), json.dumps(CURRENT_DATA, sort_keys=True), TEST_DB)

        # Test 1: Empty list
        print("\n--- Test 1: empty list ---")
        results = await semantic_diff([], TEST_DB)
        assert results == []
        print("[PASS] empty list returns []")

        # Test 2: First extraction (prior_hash=None) — skips OpenAI
        print("\n--- Test 2: first extraction (no prior) ---")
        er_first = ExtractionResult(
            node=db_node, current_json=CURRENT_DATA,
            current_hash=hash_json(CURRENT_DATA),
            status="changed", prior_hash=None,
        )
        results = await semantic_diff([er_first], TEST_DB)
        assert len(results) == 1
        assert results[0].change_type == "material"
        assert "First extraction" in results[0].change_description
        print(f"[PASS] first extraction — material, desc: {results[0].change_description}")

        # Test 3: Changed node with prior version — mock OpenAI
        print("\n--- Test 3: changed node (mock OpenAI) ---")

        async def mock_chat_json(system_prompt, user_content, model=None):
            assert "min_paid_up_capital" in user_content
            assert "250000" in user_content  # prior
            assert "500000" in user_content  # current
            return {
                "changed": True,
                "change_type": "material",
                "change_description": "Capital requirement doubled from 250k to 500k SGD",
            }

        diff_module.chat_json = mock_chat_json

        er_changed = ExtractionResult(
            node=db_node, current_json=CURRENT_DATA,
            current_hash=hash_json(CURRENT_DATA),
            status="changed", prior_hash=hash_json(PRIOR_DATA),
        )
        results = await semantic_diff([er_changed], TEST_DB)
        assert len(results) == 1
        assert results[0].changed is True
        assert results[0].change_type == "material"
        assert "doubled" in results[0].change_description
        print(f"[PASS] changed — material: {results[0].change_description}")

        # Test 4: OpenAI failure — falls back to ambiguous
        print("\n--- Test 4: OpenAI failure ---")

        async def mock_chat_json_fail(system_prompt, user_content, model=None):
            raise RuntimeError("API timeout")

        diff_module.chat_json = mock_chat_json_fail

        results = await semantic_diff([er_changed], TEST_DB)
        assert len(results) == 1
        assert results[0].change_type == "ambiguous"
        assert "failed" in results[0].change_description.lower() or "error" in results[0].change_description.lower()
        print(f"[PASS] OpenAI failure — ambiguous: {results[0].change_description}")

        # Test 5: Mixed batch
        print("\n--- Test 5: mixed batch ---")

        call_count = 0

        async def mock_chat_json_mixed(system_prompt, user_content, model=None):
            nonlocal call_count
            call_count += 1
            return {
                "changed": False,
                "change_type": "cosmetic",
                "change_description": "Formatting change only",
            }

        diff_module.chat_json = mock_chat_json_mixed

        results = await semantic_diff([er_first, er_changed], TEST_DB)
        assert len(results) == 2
        assert results[0].change_type == "material"  # first extraction, no OpenAI call
        assert results[1].change_type == "cosmetic"  # real diff via mock
        assert call_count == 1, f"Expected 1 OpenAI call (first extraction skipped), got {call_count}"
        print(f"[PASS] mixed batch — material + cosmetic, OpenAI calls: {call_count}")

        print("\n=== All Phase 6 tests passed ===")

    finally:
        diff_module.chat_json = original_chat_json
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


if __name__ == "__main__":
    asyncio.run(main())
