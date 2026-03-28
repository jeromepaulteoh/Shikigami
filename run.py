import asyncio
import json
import logging
import pathlib
import sys
from datetime import datetime, timezone

from graph import get_meta, get_nodes_by_form_fields, init_db
from layers.layer0_seed import seed_graph
from layers.layer1_canary import check_canary
from layers.layer2_extract import parallel_extract
from layers.layer3_diff import semantic_diff
from layers.layer4_form import fill_form
from layers.layer5_pdf_fill import fill_pdf
from layers.layer6_upload import upload_to_github
from layers.layer7_autofill import run_autofill

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)
ROOT = pathlib.Path(__file__).parent
FRONTEND_JSON_PATH = ROOT / "data" / "frontend_payload.json"
FRONTEND_JS_PATH = ROOT / "data" / "frontend_payload.js"


def _stringify_value(value: object) -> str:
    if value is None:
        return "Pending extraction"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        for key in ("value", "description", "title", "text", "name", "url"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return json.dumps(value, sort_keys=True)
    if isinstance(value, list):
        return ", ".join(_stringify_value(item) for item in value[:3])
    return str(value)


def _group_fields(fields: list[dict]) -> list[list[object]]:
    groups: dict[str, list[list[str]]] = {
        "Withdrawal request": [],
        "Supporting materials": [],
        "Regulatory checks": [],
    }
    for field in fields:
        description = field.get("description", "")
        confidence = field.get("confidence", "missing")
        state = "ok" if confidence == "high" else "review" if confidence == "review_required" else "missing"
        row = [
            description or field.get("field_id", "Field"),
            _stringify_value(field.get("value")),
            state,
        ]
        lowered = description.lower()
        if "document" in lowered or "pdf" in lowered or "attach" in lowered:
            groups["Supporting materials"].append(row)
        elif "eligibility" in lowered or "fee" in lowered or "criteria" in lowered:
            groups["Regulatory checks"].append(row)
        else:
            groups["Withdrawal request"].append(row)
    return [[name, rows] for name, rows in groups.items() if rows]


def _build_actions(fields: list[dict]) -> list[list[str]]:
    actions: list[list[str]] = []
    for field in fields:
        if not field.get("review"):
            continue
        tone = "warnbox" if field.get("confidence") == "missing" else "notebox"
        prefix = "Action" if tone == "warnbox" else "Note"
        description = field.get("description", field.get("field_id", "field"))
        change = field.get("change_description") or "Requires analyst confirmation before simulated fill."
        cta = "Resolved - evidence attached" if tone == "warnbox" else "Reviewed - accept updated wording"
        actions.append([tone, prefix, f"{description}: {change}", cta])
    return actions[:4]


def _build_changes(canary: dict, diff_results: list, extraction_results: list) -> list[dict]:
    changes: list[dict] = []
    for diff in diff_results:
        kind = "warn" if diff.change_type in ("material", "ambiguous") else "info"
        changes.append({
            "kind": kind,
            "title": f"Change detected for {diff.node.url}",
            "desc": diff.change_description,
            "meta": f"Semantic diff | {diff.change_type}",
        })
    if canary.get("status") == "changed":
        changes.append({
            "kind": "info",
            "title": "Top-level navigation drift detected",
            "desc": "Canary noticed site-structure drift. Maintenance rebuild should refresh the broader graph baseline.",
            "meta": "Canary status | changed but non-blocking",
        })
    unchanged = sum(1 for result in extraction_results if result.status == "unchanged")
    if unchanged:
        changes.append({
            "kind": "ok",
            "title": f"{unchanged} tracked node(s) remained stable",
            "desc": "Stable branches can be reused without manual review.",
            "meta": "Hash stable | high confidence",
        })
    if not changes:
        changes.append({
            "kind": "ok",
            "title": "No material changes detected",
            "desc": "The current run produced no diff or canary alerts.",
            "meta": "Pipeline result | clean run",
        })
    return changes


def _build_frontend_payload(
    form: dict,
    canary: dict,
    extraction_results: list,
    diff_results: list,
    filled_form: dict,
) -> dict:
    fields = filled_form.get("fields", [])
    summary = filled_form.get("summary", {})
    fill_rows = [
        [field.get("description", field.get("field_id", "Field")), _stringify_value(field.get("value"))]
        for field in fields
    ]
    total = max(summary.get("total_fields", 0), 1)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "client_name": "Atlas Restructuring Pte Ltd",
        "workflow_name": form.get("form_name", "Withdrawal from Being Approved Liquidators"),
        "breadcrumb_name": "Atlas Restructuring",
        "canary_status": canary.get("status", "stable"),
        "stats": [
            ["Tracked fields", str(summary.get("total_fields", 0)), ""],
            ["Review required", str(summary.get("review_required", 0)), "warn"],
            ["Missing", str(summary.get("missing", 0)), "warn"],
            ["High confidence", str(summary.get("high_confidence", 0)), "ok"],
        ],
        "table": [
            [
                "Atlas Restructuring Pte Ltd",
                form.get("form_name", "Withdrawal from Being Approved Liquidators"),
                datetime.now().strftime("%d %b %Y, %I:%M %p"),
                f"{len(diff_results)} changes" if diff_results else "stable",
                "warn" if diff_results else "ok",
                "graph refresh" if canary.get("status") == "changed" else "none",
            ]
        ],
        "changes": _build_changes(canary, diff_results, extraction_results),
        "uploads": [
            ["acra_withdrawal_form.pdf", "Simulated preprocess", "OpenAI derives structured fields and TinyFish goals from the uploaded form"],
            ["supporting_statement.pdf", "Simulated preprocess", "Narrative grounds are normalized into reviewable field context"],
            ["regulatory_correspondence.pdf", "Simulated preprocess", "References are linked to graph nodes for deeper trace"],
        ],
        "groups": _group_fields(fields),
        "actions": _build_actions(fields),
        "fill": fill_rows,
        "summary": {
            "changes": len(diff_results),
            "rebuilds": 1 if canary.get("status") == "changed" or diff_results else 0,
            "simulated_fields": len(fill_rows),
            "real_submissions": 0,
            "completion_ratio": summary.get("high_confidence", 0) / total,
        },
    }


def emit_frontend_payload(payload: dict) -> None:
    FRONTEND_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_JSON_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    FRONTEND_JS_PATH.write_text(
        "window.REGULATOR_PAYLOAD = " + json.dumps(payload, indent=2) + ";\n",
        encoding="utf-8",
    )
    logger.info("Frontend payload written to %s and %s", FRONTEND_JSON_PATH, FRONTEND_JS_PATH)


async def run_compliance(form_path: str) -> dict:
    """Run the full compliance pipeline and emit a frontend-ready payload."""
    form = json.loads(pathlib.Path(form_path).read_text(encoding="utf-8"))
    form_id = form["form_id"]

    await init_db()

    if not await get_meta(f"seeded:{form_id}"):
        logger.info("First run for form %s, seeding graph", form_id)
        await seed_graph(form_path)
    else:
        logger.info("Graph already seeded for form %s", form_id)

    canary = await check_canary()
    logger.info("Canary result: %s", canary["status"])

    field_ids = [f["field_id"] for f in form["fields"]]
    nodes = await get_nodes_by_form_fields(field_ids)
    logger.info("Found %d nodes for %d form fields", len(nodes), len(field_ids))

    extraction_results = await parallel_extract(nodes)
    changed = [result for result in extraction_results if result.status == "changed"]
    diff_results = await semantic_diff(changed) if changed else []

    pipeline_output = fill_form(form, extraction_results, diff_results)

    # Phase 10: PDF fill → GitHub upload → TinyFish autofill
    pdf_src = str(ROOT / "data" / "CSP_Update registered qualified individual information.pdf")
    pdf_dst = str(ROOT / "data" / "filled" / "CSP_Update_filled.pdf")
    filled_pdf_path = await fill_pdf(pdf_src, pipeline_output["fields"], pdf_dst)
    logger.info("Filled PDF: %s", filled_pdf_path)

    pdf_url = await upload_to_github(filled_pdf_path)
    logger.info("PDF uploaded to GitHub: %s", pdf_url)

    autofill_result = await run_autofill(
        "http://localhost:8080/form.html", pipeline_output, pdf_url,
    )
    pipeline_output["autofill"] = autofill_result

    frontend_payload = _build_frontend_payload(form, canary, extraction_results, diff_results, pipeline_output)
    emit_frontend_payload(frontend_payload)

    print(json.dumps(pipeline_output, indent=2))
    return {
        "pipeline_output": pipeline_output,
        "frontend_payload": frontend_payload,
    }


if __name__ == "__main__":
    form_path = sys.argv[1] if len(sys.argv) > 1 else "sample_form.json"
    asyncio.run(run_compliance(form_path))
