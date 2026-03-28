import json
import logging
import pathlib

from graph import Node, init_db, upsert_node, get_meta, set_meta
from clients.openai_client import chat_json

logger = logging.getLogger(__name__)

SEED_SYSTEM_PROMPT = """You are a regulatory compliance assistant. Given this compliance form definition,
produce a JSON with:
1. seed_url: the government/regulatory authority URL to start navigation from
2. For each field, a target URL on the authority's website and a plain English extraction goal

Return ONLY valid JSON, no markdown, no preamble.

Return format:
{
  "seed_url": "https://www.example.gov.sg/...",
  "nodes": [
    {
      "field_id": "...",
      "url": "...",
      "extraction_goal": "Find ... Return JSON with the relevant details."
    }
  ]
}"""


async def seed_graph(form_path: str, db_path: str | None = None) -> list[Node]:
    """Load form JSON, call OpenAI for navigation skeleton, write nodes to graph.

    Idempotent: skips if already seeded for this form_id.
    Returns list of created Node objects, or empty list if already seeded.
    """
    form = json.loads(pathlib.Path(form_path).read_text())
    form_id = form["form_id"]

    await init_db(db_path)

    # Idempotency check
    meta_key = f"seeded:{form_id}"
    if await get_meta(meta_key, db_path):
        logger.info("Graph already seeded for form %s, skipping", form_id)
        return []

    # Call OpenAI for navigation skeleton
    skeleton = await chat_json(
        system_prompt=SEED_SYSTEM_PROMPT,
        user_content=f"Form: {json.dumps(form, indent=2)}",
    )

    seed_url = skeleton.get("seed_url")
    nodes_data = skeleton.get("nodes", [])
    if not seed_url or not nodes_data:
        raise ValueError(f"Invalid OpenAI response: missing seed_url or nodes. Got: {skeleton}")

    # Write seed node (depth 0)
    seed_node = Node(
        url=seed_url,
        extraction_goal=f"Navigation seed - {form.get('form_name', 'regulatory')} landing page",
        depth_from_seed=0,
    )
    await upsert_node(seed_node, db_path)

    # Write per-field nodes (depth 1)
    created = [seed_node]
    for item in nodes_data:
        node = Node(
            url=item["url"],
            parent_url=seed_url,
            extraction_goal=item["extraction_goal"],
            depth_from_seed=1,
            relevant_form_fields=json.dumps([item["field_id"]]),
        )
        await upsert_node(node, db_path)
        created.append(node)

    # Mark as seeded
    await set_meta(meta_key, json.dumps({
        "form_id": form_id,
        "seed_url": seed_url,
        "node_count": len(nodes_data),
    }), db_path)

    logger.info("Seeded %d nodes for form %s", len(nodes_data) + 1, form_id)
    return created
