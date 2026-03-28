import asyncio
import json
import logging
from dataclasses import dataclass

from clients.openai_client import chat_json
from graph import get_node, get_prior_version, init_db
from graph.models import Node
from layers.layer2_extract import ExtractionResult

logger = logging.getLogger(__name__)

DIFF_SYSTEM_PROMPT = """You are a regulatory compliance analyst. Compare two regulatory extracts and determine if the change is material.

Return ONLY valid JSON:
{"changed": true | false, "change_type": "material" | "cosmetic" | "ambiguous", "change_description": "plain English description"}"""


@dataclass
class DiffResult:
    node: Node
    changed: bool
    change_type: str        # material | cosmetic | ambiguous
    change_description: str
    current_json: dict


async def _diff_single(er: ExtractionResult, db_path: str | None = None) -> DiffResult:
    """Run semantic diff for a single changed ExtractionResult."""
    # First extraction — no prior to compare
    if er.prior_hash is None:
        return DiffResult(
            node=er.node, changed=True, change_type="material",
            change_description="First extraction — no prior version to compare",
            current_json=er.current_json,
        )

    # Get prior JSON from node_versions
    db_node = await get_node(er.node.url, db_path)
    if db_node is None or db_node.id is None:
        return DiffResult(
            node=er.node, changed=True, change_type="ambiguous",
            change_description="Could not retrieve node from DB",
            current_json=er.current_json,
        )

    prior_json_str = await get_prior_version(db_node.id, db_path)
    if prior_json_str is None:
        return DiffResult(
            node=er.node, changed=True, change_type="material",
            change_description="Prior version not found in history",
            current_json=er.current_json,
        )

    prior_json = json.loads(prior_json_str)

    # Parse field_id from node
    field_id = "unknown"
    if er.node.relevant_form_fields:
        try:
            fields = json.loads(er.node.relevant_form_fields)
            field_id = ", ".join(fields) if fields else "unknown"
        except (json.JSONDecodeError, TypeError):
            pass

    # Call OpenAI for semantic diff
    user_content = (
        f"Compare these two regulatory extracts for field '{field_id}'.\n\n"
        f"Prior: {json.dumps(prior_json, indent=2)}\n\n"
        f"Current: {json.dumps(er.current_json, indent=2)}\n\n"
        "Did the regulatory requirement change?"
    )

    try:
        result = await chat_json(DIFF_SYSTEM_PROMPT, user_content)
        return DiffResult(
            node=er.node,
            changed=result.get("changed", True),
            change_type=result.get("change_type", "ambiguous"),
            change_description=result.get("change_description", "No description provided"),
            current_json=er.current_json,
        )
    except Exception as e:
        logger.error("OpenAI diff failed for %s: %s", er.node.url, e)
        return DiffResult(
            node=er.node, changed=True, change_type="ambiguous",
            change_description=f"Diff failed: {e}",
            current_json=er.current_json,
        )


async def semantic_diff(changed_results: list[ExtractionResult], db_path: str | None = None) -> list[DiffResult]:
    """Run semantic diff on all changed ExtractionResults in parallel."""
    if not changed_results:
        return []

    await init_db(db_path)

    tasks = [_diff_single(er, db_path) for er in changed_results]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    final = []
    for er, result in zip(changed_results, results):
        if isinstance(result, Exception):
            logger.error("Unexpected error diffing %s: %s", er.node.url, result)
            final.append(DiffResult(
                node=er.node, changed=True, change_type="ambiguous",
                change_description=f"Unexpected error: {result}",
                current_json=er.current_json,
            ))
        else:
            final.append(result)

    logger.info(
        "Semantic diff complete: %d total, %d material, %d cosmetic, %d ambiguous",
        len(final),
        sum(1 for r in final if r.change_type == "material"),
        sum(1 for r in final if r.change_type == "cosmetic"),
        sum(1 for r in final if r.change_type == "ambiguous"),
    )
    return final
