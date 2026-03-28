import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graph import init_db, get_node, get_nodes_by_form_fields, get_meta
from layers.layer0_seed import seed_graph

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

TEST_DB = "test_regflow.db"
FORM_PATH = os.path.join(os.path.dirname(__file__), "..", "sample_form.json")


async def main():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    try:
        # 1. Seed the graph
        print("\n--- Test 1: seed_graph (real OpenAI call) ---")
        nodes = await seed_graph(FORM_PATH, TEST_DB)
        assert len(nodes) >= 4, f"Expected at least 4 nodes (1 seed + 3 fields), got {len(nodes)}"
        print(f"[PASS] seed_graph — created {len(nodes)} nodes")

        # 2. Verify seed node exists
        print("\n--- Test 2: seed node in DB ---")
        seed_node = nodes[0]
        fetched = await get_node(seed_node.url, TEST_DB)
        assert fetched is not None, "Seed node not found in DB"
        assert fetched.depth_from_seed == 0, f"Seed depth should be 0, got {fetched.depth_from_seed}"
        print(f"[PASS] seed node — url={fetched.url}, depth={fetched.depth_from_seed}")

        # 3. Verify field nodes (check structure, not exact field_id matching — OpenAI may vary)
        print("\n--- Test 3: field nodes in DB ---")
        field_nodes = [n for n in nodes if n.depth_from_seed == 1]
        assert len(field_nodes) >= 3, f"Expected at least 3 field nodes, got {len(field_nodes)}"
        for node in field_nodes:
            assert node.extraction_goal is not None, f"extraction_goal is None for {node.url}"
            assert node.parent_url is not None, f"parent_url is None for {node.url}"
            assert node.relevant_form_fields is not None, f"relevant_form_fields is None for {node.url}"
            fields = json.loads(node.relevant_form_fields)
            assert len(fields) >= 1, f"relevant_form_fields is empty for {node.url}"
            print(f"[PASS] field node — field={fields[0]}, url={node.url}")

        # 4. Verify idempotency
        print("\n--- Test 4: idempotency ---")
        meta = await get_meta("seeded:MAS_AML_MVP", TEST_DB)
        assert meta is not None, "seeded meta key not set"

        nodes2 = await seed_graph(FORM_PATH, TEST_DB)
        assert nodes2 == [], f"Expected empty list on re-seed, got {len(nodes2)} nodes"
        print("[PASS] idempotency — second seed returned empty list")

        # 5. Print all nodes for inspection
        print("\n--- Seeded nodes summary ---")
        for n in nodes:
            print(f"  depth={n.depth_from_seed}  url={n.url}")
            if n.extraction_goal:
                print(f"    goal: {n.extraction_goal[:80]}...")

        print("\n=== All Phase 3 tests passed ===")

    finally:
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


if __name__ == "__main__":
    asyncio.run(main())
