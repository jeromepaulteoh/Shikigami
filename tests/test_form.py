import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graph.models import Node
from layers.layer2_extract import ExtractionResult
from layers.layer3_diff import DiffResult
from layers.layer4_form import fill_form

FORM = {
    "form_id": "TEST_FORM",
    "form_name": "Test Form",
    "fields": [
        {"field_id": "field_a", "description": "Field A"},
        {"field_id": "field_b", "description": "Field B"},
        {"field_id": "field_c", "description": "Field C"},
        {"field_id": "field_d", "description": "Field D"},
        {"field_id": "field_missing", "description": "No node maps here"},
    ],
}


def make_node(url, field_ids):
    return Node(url=url, relevant_form_fields=json.dumps(field_ids), depth_from_seed=1)


def main():
    # Setup: nodes and results
    node_a = make_node("https://example.com/a", ["field_a"])
    node_b = make_node("https://example.com/b", ["field_b"])
    node_c = make_node("https://example.com/c", ["field_c"])
    node_d = make_node("https://example.com/d", ["field_d"])

    er_unchanged = ExtractionResult(
        node=node_a, current_json={"val": "100"}, current_hash="aaa",
        status="unchanged", prior_hash="aaa",
    )
    er_changed_material = ExtractionResult(
        node=node_b, current_json={"val": "200"}, current_hash="bbb",
        status="changed", prior_hash="old_bbb",
    )
    er_changed_cosmetic = ExtractionResult(
        node=node_c, current_json={"val": "300"}, current_hash="ccc",
        status="changed", prior_hash="old_ccc",
    )
    er_error = ExtractionResult(
        node=node_d, current_json={}, current_hash="",
        status="error_other", prior_hash="ddd",
    )

    dr_material = DiffResult(
        node=node_b, changed=True, change_type="material",
        change_description="Value doubled", current_json={"val": "200"},
    )
    dr_cosmetic = DiffResult(
        node=node_c, changed=False, change_type="cosmetic",
        change_description="Formatting only", current_json={"val": "300"},
    )

    extraction_results = [er_unchanged, er_changed_material, er_changed_cosmetic, er_error]
    diff_results = [dr_material, dr_cosmetic]

    # Test 1: Full mixed form filling
    print("\n--- Test 1: mixed form filling ---")
    output = fill_form(FORM, extraction_results, diff_results)

    assert output["form_id"] == "TEST_FORM"
    assert output["form_name"] == "Test Form"
    assert "filled_at" in output
    assert len(output["fields"]) == 5

    fields = {f["field_id"]: f for f in output["fields"]}

    # field_a: unchanged → high, no review
    assert fields["field_a"]["confidence"] == "high"
    assert fields["field_a"]["review"] is False
    assert fields["field_a"]["value"] == {"val": "100"}
    print("[PASS] field_a — unchanged, high confidence")

    # field_b: material change → review_required
    assert fields["field_b"]["confidence"] == "review_required"
    assert fields["field_b"]["review"] is True
    assert fields["field_b"]["change_description"] == "Value doubled"
    assert fields["field_b"]["value"] == {"val": "200"}
    print("[PASS] field_b — material change, review required")

    # field_c: cosmetic change → high
    assert fields["field_c"]["confidence"] == "high"
    assert fields["field_c"]["review"] is False
    assert fields["field_c"]["change_description"] == "Formatting only"
    print("[PASS] field_c — cosmetic change, high confidence")

    # field_d: error → missing
    assert fields["field_d"]["confidence"] == "missing"
    assert fields["field_d"]["review"] is True
    assert fields["field_d"]["value"] is None
    print("[PASS] field_d — error, missing")

    # field_missing: no node → missing
    assert fields["field_missing"]["confidence"] == "missing"
    assert fields["field_missing"]["review"] is True
    assert fields["field_missing"]["value"] is None
    print("[PASS] field_missing — no node, missing")

    # Test 2: Summary counts
    print("\n--- Test 2: summary ---")
    s = output["summary"]
    assert s["total_fields"] == 5
    assert s["high_confidence"] == 2     # unchanged + cosmetic
    assert s["review_required"] == 1     # material
    assert s["missing"] == 2             # error + no node
    print(f"[PASS] summary — total={s['total_fields']}, high={s['high_confidence']}, review={s['review_required']}, missing={s['missing']}")

    # Test 3: Empty inputs
    print("\n--- Test 3: empty inputs ---")
    empty_out = fill_form(FORM, [], [])
    assert len(empty_out["fields"]) == 5
    assert all(f["confidence"] == "missing" for f in empty_out["fields"])
    assert empty_out["summary"]["missing"] == 5
    print("[PASS] empty inputs — all fields missing")

    # Test 4: Ambiguous diff → review_required
    print("\n--- Test 4: ambiguous diff ---")
    dr_ambiguous = DiffResult(
        node=node_b, changed=True, change_type="ambiguous",
        change_description="Unclear change", current_json={"val": "200"},
    )
    out = fill_form(FORM, [er_changed_material], [dr_ambiguous])
    fb = next(f for f in out["fields"] if f["field_id"] == "field_b")
    assert fb["confidence"] == "review_required"
    assert fb["review"] is True
    print("[PASS] ambiguous — review required")

    # Test 5: Multiple nodes for same field — prefer successful
    print("\n--- Test 5: multiple nodes, prefer successful ---")
    node_d2 = make_node("https://example.com/d2", ["field_d"])
    er_d2_ok = ExtractionResult(
        node=node_d2, current_json={"val": "good"}, current_hash="d2d2",
        status="unchanged", prior_hash="d2d2",
    )
    out = fill_form(FORM, [er_error, er_d2_ok], [])
    fd = next(f for f in out["fields"] if f["field_id"] == "field_d")
    assert fd["confidence"] == "high"
    assert fd["value"] == {"val": "good"}
    print("[PASS] multiple nodes — successful preferred over error")

    print("\n=== All Phase 7 tests passed ===")


if __name__ == "__main__":
    main()
