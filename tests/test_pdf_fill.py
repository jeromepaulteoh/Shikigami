import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from layers.layer5_pdf_fill import fill_pdf, map_fields_with_openai

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

PDF_SRC = os.path.join(os.path.dirname(__file__), "..", "data", "CSP_Update registered qualified individual information.pdf")
PDF_DST = os.path.join(os.path.dirname(__file__), "..", "data", "filled", "CSP_Update_test_filled.pdf")

MOCK_FORM_FIELDS = [
    {"field_id": "lodgement_description", "description": "Lodgement description", "value": "Withdrawal from Being Approved Liquidators", "confidence": "high", "review": False, "change_description": None},
    {"field_id": "required_form_pdf", "description": "Required PDF form", "value": "CSP_Update form", "confidence": "high", "review": False, "change_description": None},
    {"field_id": "eligibility_criteria", "description": "Eligibility criteria", "value": "Must have no outstanding appointments", "confidence": "review_required", "review": True, "change_description": "Updated wording"},
]

MOCK_FIELD_MAP = {
    "Name": "Rachel Tan",
    "Identification No": "S1234567A",
    "Email Address": "jerometeoh@gmail.com",
    "Mobile Number": "91234567",
}


async def main():
    passed = 0
    failed = 0

    # Mock OpenAI to avoid live calls
    import layers.layer5_pdf_fill as pdf_module
    original_map = pdf_module.map_fields_with_openai

    async def mock_map(form_fields):
        return MOCK_FIELD_MAP

    try:
        # Test 1: fill_pdf with mocked OpenAI produces a valid PDF
        print("\n--- Test 1: fill_pdf produces output file ---")
        pdf_module.map_fields_with_openai = mock_map

        if os.path.exists(PDF_DST):
            os.remove(PDF_DST)

        result_path = await fill_pdf(PDF_SRC, MOCK_FORM_FIELDS, PDF_DST)
        assert os.path.exists(result_path), f"Output PDF not found at {result_path}"
        assert os.path.getsize(result_path) > 0, "Output PDF is empty"
        print(f"  PASS: PDF written to {result_path} ({os.path.getsize(result_path)} bytes)")
        passed += 1

        # Test 2: verify filled fields are readable
        print("\n--- Test 2: filled fields are present in output PDF ---")
        from pypdf import PdfReader
        reader = PdfReader(result_path)
        fields = reader.get_fields()
        assert fields is not None, "No fields in output PDF"
        name_field = fields.get("Name")
        assert name_field is not None, "Name field missing"
        print(f"  PASS: Output PDF has {len(fields)} fields")
        passed += 1

        # Test 3: fill_pdf with empty field map writes valid PDF
        print("\n--- Test 3: fill_pdf with no mapped fields ---")
        async def mock_empty_map(form_fields):
            return {}

        pdf_module.map_fields_with_openai = mock_empty_map
        empty_dst = PDF_DST.replace("_test_filled", "_test_empty")
        result_path = await fill_pdf(PDF_SRC, [], empty_dst)
        assert os.path.exists(result_path), "Empty-fill PDF not found"
        print(f"  PASS: Empty-fill PDF written ({os.path.getsize(result_path)} bytes)")
        passed += 1

        # Cleanup
        for path in [PDF_DST, empty_dst]:
            if os.path.exists(path):
                os.remove(path)

    finally:
        pdf_module.map_fields_with_openai = original_map

    print(f"\n{'='*40}")
    print(f"PDF Fill Tests: {passed} passed, {failed} failed")
    assert failed == 0, f"{failed} test(s) failed"


if __name__ == "__main__":
    asyncio.run(main())
