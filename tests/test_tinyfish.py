import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from clients.tinyfish import TinyFishClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def main():
    client = TinyFishClient()

    # Test 1: run_single via SSE
    print("\n--- Test 1: run_single (SSE) ---")
    result = await client.run_single(
        url="https://www.mas.gov.sg/regulation",
        goal="Return the page title and the first 3 navigation links as JSON: {title, links: [{text, href}]}",
    )
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "error" not in result, f"run_single returned error: {result}"
    print(f"[PASS] run_single — result: {result}")

    # Test 2: run_single error handling (bad URL)
    print("\n--- Test 2: run_single error handling ---")
    err_result = await client.run_single(
        url="https://www.mas.gov.sg/this-page-does-not-exist-at-all-404",
        goal="Return the page title as JSON",
    )
    assert isinstance(err_result, dict), f"Expected dict, got {type(err_result)}"
    # Should either return content or a graceful error — must not raise
    print(f"[PASS] run_single error — result: {err_result}")

    # Test 3: run_batch via /run-batch + polling
    print("\n--- Test 3: run_batch ---")
    tasks = [
        {"url": "https://www.mas.gov.sg/regulation", "goal": "Return the page title as JSON: {title}"},
        {"url": "https://www.mas.gov.sg", "goal": "Return the page title as JSON: {title}"},
    ]
    batch_results = await client.run_batch(tasks)
    assert isinstance(batch_results, list), f"Expected list, got {type(batch_results)}"
    assert len(batch_results) == 2, f"Expected 2 results, got {len(batch_results)}"
    print(f"[PASS] run_batch — results: {batch_results}")

    print("\n=== All Phase 2 tests passed ===")


if __name__ == "__main__":
    asyncio.run(main())
