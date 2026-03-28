import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from clients.tinyfish import TinyFishClient
from graph import init_db, upsert_node, get_node, save_version, update_node_url, hash_json
from graph.models import Node

logger = logging.getLogger(__name__)

BATCH_SIZE = 100  # TinyFish API limit per batch
MAX_REPAIRS = 5   # Cap repair attempts per run to control API costs


@dataclass
class ExtractionResult:
    node: Node
    current_json: dict
    current_hash: str
    status: str        # "unchanged" | "changed" | "error_404" | "error_other"
    prior_hash: str | None


async def parallel_extract(nodes: list[Node], db_path: str | None = None) -> list[ExtractionResult]:
    """Fan out TinyFish across all nodes, hash and triage results.

    Updates DB for every node: content_hash, last_extracted_json, last_extracted_at.
    Calls save_version for every successful extraction.
    Attempts repair on error results (up to MAX_REPAIRS).
    """
    if not nodes:
        return []

    await init_db(db_path)
    client = TinyFishClient()

    # Build batch tasks
    tasks = [
        {"url": node.url, "goal": node.extraction_goal or "", "browser_profile": "stealth"}
        for node in nodes
    ]

    # Submit in chunks of BATCH_SIZE
    raw_results = []
    for i in range(0, len(tasks), BATCH_SIZE):
        chunk = tasks[i:i + BATCH_SIZE]
        try:
            chunk_results = await client.run_batch(chunk)
            raw_results.extend(chunk_results)
        except Exception as e:
            logger.error("run_batch failed for chunk %d-%d: %s", i, i + len(chunk), e)
            raw_results.extend([{"error": "failed", "url": t["url"]} for t in chunk])

    # Triage each result
    results = []
    now = datetime.now(timezone.utc).isoformat()

    for node, raw in zip(nodes, raw_results):
        prior_hash = node.content_hash

        if "error" in raw:
            result = ExtractionResult(
                node=node, current_json={}, current_hash="",
                status="error_other", prior_hash=prior_hash,
            )
            node.last_extracted_at = now
            await upsert_node(node, db_path)
        else:
            current_hash = hash_json(raw)
            json_str = json.dumps(raw, sort_keys=True)

            if prior_hash is None or prior_hash != current_hash:
                status = "changed"
            else:
                status = "unchanged"

            result = ExtractionResult(
                node=node, current_json=raw, current_hash=current_hash,
                status=status, prior_hash=prior_hash,
            )

            node.content_hash = current_hash
            node.last_extracted_json = json_str
            node.last_extracted_at = now
            await upsert_node(node, db_path)

            db_node = await get_node(node.url, db_path)
            if db_node and db_node.id is not None:
                await save_version(db_node.id, current_hash, json_str, db_path)

        results.append(result)

    # Attempt repair on error results
    error_indices = [i for i, r in enumerate(results) if r.status.startswith("error")]
    if error_indices:
        to_repair = [results[i] for i in error_indices[:MAX_REPAIRS]]
        if len(error_indices) > MAX_REPAIRS:
            logger.warning("Capping repair attempts at %d (of %d errors)", MAX_REPAIRS, len(error_indices))
        repaired = await repair_404(to_repair, db_path)
        for idx, repaired_result in zip(error_indices[:MAX_REPAIRS], repaired):
            results[idx] = repaired_result

    logger.info(
        "Extraction complete: %d total, %d changed, %d unchanged, %d errors",
        len(results),
        sum(1 for r in results if r.status == "changed"),
        sum(1 for r in results if r.status == "unchanged"),
        sum(1 for r in results if r.status.startswith("error")),
    )
    return results


async def _repair_single(er: ExtractionResult, db_path: str | None = None) -> ExtractionResult:
    """Attempt to repair a single failed extraction by finding the new URL via parent."""
    node = er.node

    if not node.parent_url:
        logger.info("Skipping repair for %s: no parent_url", node.url)
        return er

    old_url = node.url
    client = TinyFishClient()

    # Ask TinyFish to find where the content moved
    repair_goal = (
        f"The page at {old_url} is no longer accessible. "
        f"Find where this content has moved: {node.extraction_goal}. "
        f"Return JSON with keys 'new_url' and 'content'."
    )

    try:
        repair_response = await client.run_single(node.parent_url, repair_goal)
    except Exception as e:
        logger.error("Repair call failed for %s: %s", old_url, e)
        return er

    if "error" in repair_response:
        logger.warning("Repair failed for %s: TinyFish returned error", old_url)
        return er

    new_url = repair_response.get("new_url")
    if not new_url or not isinstance(new_url, str) or not new_url.startswith("http"):
        logger.warning("Repair failed for %s: no valid new_url in response: %s", old_url, repair_response)
        return er

    # Update URL in graph
    success = await update_node_url(old_url, new_url, db_path)
    if not success:
        logger.warning("URL update failed for %s -> %s (conflict or not found)", old_url, new_url)
        return er

    logger.info("Repaired URL: %s -> %s", old_url, new_url)
    node.url = new_url

    # Re-extract from new URL
    try:
        re_result = await client.run_single(new_url, node.extraction_goal or "")
    except Exception as e:
        logger.error("Re-extraction failed at %s: %s", new_url, e)
        return ExtractionResult(
            node=node, current_json={}, current_hash="",
            status="error_other", prior_hash=er.prior_hash,
        )

    if "error" in re_result:
        logger.warning("Re-extraction failed at new URL %s", new_url)
        return ExtractionResult(
            node=node, current_json={}, current_hash="",
            status="error_other", prior_hash=er.prior_hash,
        )

    # Success — hash, update DB, save version
    now = datetime.now(timezone.utc).isoformat()
    current_hash = hash_json(re_result)
    json_str = json.dumps(re_result, sort_keys=True)
    prior_hash = er.prior_hash

    status = "changed" if prior_hash is None or prior_hash != current_hash else "unchanged"

    node.content_hash = current_hash
    node.last_extracted_json = json_str
    node.last_extracted_at = now
    await upsert_node(node, db_path)

    db_node = await get_node(new_url, db_path)
    if db_node and db_node.id is not None:
        await save_version(db_node.id, current_hash, json_str, db_path)

    return ExtractionResult(
        node=node, current_json=re_result, current_hash=current_hash,
        status=status, prior_hash=prior_hash,
    )


async def repair_404(
    error_results: list[ExtractionResult], db_path: str | None = None
) -> list[ExtractionResult]:
    """Attempt repair on failed extractions by navigating from parent_url."""
    if not error_results:
        return []

    logger.info("Attempting repair on %d error results", len(error_results))
    tasks = [_repair_single(er, db_path) for er in error_results]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    final = []
    for er, result in zip(error_results, results):
        if isinstance(result, Exception):
            logger.error("Unexpected error during repair of %s: %s", er.node.url, result)
            final.append(er)
        else:
            final.append(result)

    repaired_count = sum(1 for r in final if not r.status.startswith("error"))
    logger.info("Repair complete: %d/%d successfully repaired", repaired_count, len(error_results))
    return final
