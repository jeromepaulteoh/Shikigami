import json
import logging
from datetime import datetime, timezone

from layers.layer2_extract import ExtractionResult
from layers.layer3_diff import DiffResult

logger = logging.getLogger(__name__)


def _classify(er: ExtractionResult | None, dr: DiffResult | None) -> tuple[str, bool, str | None]:
    """Classify confidence for a form field.

    Returns (confidence, review, change_description).
    """
    if er is None:
        return ("missing", True, None)

    if er.status in ("error_404", "error_other"):
        return ("missing", True, None)

    if er.status == "unchanged":
        return ("high", False, None)

    # status == "changed"
    if dr is None:
        return ("review_required", True, "Changed but no diff available")

    if dr.change_type == "cosmetic":
        return ("high", False, dr.change_description)
    elif dr.change_type == "material":
        return ("review_required", True, dr.change_description)
    else:  # ambiguous
        return ("review_required", True, dr.change_description)


def fill_form(
    form: dict,
    extraction_results: list[ExtractionResult],
    diff_results: list[DiffResult],
) -> dict:
    """Map extraction and diff results to form fields with confidence scoring."""

    # Build index: field_id -> list of ExtractionResults
    field_to_ers: dict[str, list[ExtractionResult]] = {}
    for er in extraction_results:
        if er.node.relevant_form_fields:
            try:
                field_ids = json.loads(er.node.relevant_form_fields)
                for fid in field_ids:
                    field_to_ers.setdefault(fid, []).append(er)
            except (json.JSONDecodeError, TypeError):
                continue

    # Build index: node url -> DiffResult
    dr_by_url: dict[str, DiffResult] = {}
    for dr in diff_results:
        dr_by_url[dr.node.url] = dr

    # Fill each form field
    filled_fields = []
    for field_def in form.get("fields", []):
        field_id = field_def["field_id"]
        ers = field_to_ers.get(field_id, [])

        # Pick best ER: prefer successful over error
        er = None
        for candidate in ers:
            if candidate.status not in ("error_404", "error_other"):
                er = candidate
                break
        if er is None and ers:
            er = ers[0]  # fall back to error ER if that's all we have

        dr = dr_by_url.get(er.node.url) if er else None

        confidence, review, change_desc = _classify(er, dr)

        # Determine value
        if dr is not None:
            value = dr.current_json
        elif er is not None and er.status not in ("error_404", "error_other"):
            value = er.current_json
        else:
            value = None

        filled_fields.append({
            "field_id": field_id,
            "description": field_def.get("description", ""),
            "value": value,
            "confidence": confidence,
            "review": review,
            "change_description": change_desc,
        })

    # Summary
    summary = {
        "total_fields": len(filled_fields),
        "high_confidence": sum(1 for f in filled_fields if f["confidence"] == "high"),
        "review_required": sum(1 for f in filled_fields if f["confidence"] == "review_required"),
        "missing": sum(1 for f in filled_fields if f["confidence"] == "missing"),
    }

    return {
        "form_id": form.get("form_id", ""),
        "form_name": form.get("form_name", ""),
        "filled_at": datetime.now(timezone.utc).isoformat(),
        "fields": filled_fields,
        "summary": summary,
    }
