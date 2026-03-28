import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from layers.layer7_autofill import build_autofill_goal, run_autofill
from clients.tinyfish import TinyFishClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

MOCK_FORM_OUTPUT = {
    "form_id": "ACRA_WITHDRAWAL_LIQUIDATOR",
    "form_name": "Withdrawal from Being Approved Liquidators",
    "fields": [
        {"field_id": "lodgement_description", "description": "Lodgement description", "value": "Withdrawal from Being Approved Liquidators", "confidence": "high", "review": False, "change_description": None},
        {"field_id": "required_form_pdf", "description": "Required PDF form", "value": "CSP_Update form", "confidence": "high", "review": False, "change_description": None},
    ],
    "summary": {"total_fields": 5, "high_confidence": 2, "review_required": 2, "missing": 1},
}

MOCK_PDF_URL = "https://raw.githubusercontent.com/jeromepaulteoh/Shikigami/main/data/filled/CSP_Update_filled.pdf"


async def main():
    passed = 0
    failed = 0

    original_run_single = TinyFishClient.run_single

    try:
        # Test 1: build_autofill_goal includes all required elements
        print("\n--- Test 1: build_autofill_goal contains required elements ---")
        goal = build_autofill_goal(MOCK_FORM_OUTPUT, MOCK_PDF_URL)
        assert "Email address" in goal, "Goal missing email instruction"
        assert "Description of lodgement" in goal, "Goal missing description instruction"
        assert "Date of document" in goal, "Goal missing date instruction"
        assert MOCK_PDF_URL in goal, "Goal missing PDF URL"
        assert "Review and confirm" in goal, "Goal missing submit instruction"
        assert "Withdrawal from Being Approved Liquidators" in goal, "Goal missing lodgement description value"
        print(f"  PASS: Goal has all required elements ({len(goal)} chars)")
        passed += 1

        # Test 2: build_autofill_goal truncates long descriptions
        print("\n--- Test 2: long description truncated to 200 chars ---")
        long_output = {
            "fields": [
                {"field_id": "lodgement_description", "value": "A" * 300, "description": "desc"},
            ],
        }
        goal = build_autofill_goal(long_output, MOCK_PDF_URL)
        assert "A" * 200 in goal, "Description not truncated correctly"
        assert "A" * 201 not in goal, "Description exceeds 200 chars"
        print("  PASS: Description truncated to 200 chars")
        passed += 1

        # Test 3: build_autofill_goal with missing lodgement_description uses fallback
        print("\n--- Test 3: fallback description when field missing ---")
        empty_output = {"fields": []}
        goal = build_autofill_goal(empty_output, MOCK_PDF_URL)
        assert "Withdrawal from Being Approved Liquidators" in goal, "Fallback description missing"
        print("  PASS: Fallback description used")
        passed += 1

        # Test 4: run_autofill calls TinyFish with correct args (mocked)
        print("\n--- Test 4: run_autofill calls TinyFish correctly ---")
        captured = {}

        async def mock_run_single(self, url, goal, browser_profile="stealth"):
            captured["url"] = url
            captured["goal"] = goal
            captured["browser_profile"] = browser_profile
            return {"status": "COMPLETED", "result": {"filled": True}}

        TinyFishClient.run_single = mock_run_single
        result = await run_autofill("http://localhost:8080/form.html", MOCK_FORM_OUTPUT, MOCK_PDF_URL)
        assert captured["url"] == "http://localhost:8080/form.html", "Wrong URL passed to TinyFish"
        assert "stealth" == captured["browser_profile"], "Wrong browser profile"
        assert result.get("status") == "COMPLETED" or result.get("result"), "Unexpected result"
        print("  PASS: TinyFish called with correct args")
        passed += 1

        # Test 5: run_autofill handles TinyFish failure gracefully
        print("\n--- Test 5: run_autofill handles failure ---")

        async def mock_fail(self, url, goal, browser_profile="stealth"):
            return {"error": "failed", "url": url}

        TinyFishClient.run_single = mock_fail
        result = await run_autofill("http://localhost:8080/form.html", MOCK_FORM_OUTPUT, MOCK_PDF_URL)
        assert result.get("error") == "failed", "Error not propagated"
        print("  PASS: Failure handled gracefully")
        passed += 1

    finally:
        TinyFishClient.run_single = original_run_single

    print(f"\n{'='*40}")
    print(f"Autofill Tests: {passed} passed, {failed} failed")
    assert failed == 0, f"{failed} test(s) failed"


if __name__ == "__main__":
    asyncio.run(main())
