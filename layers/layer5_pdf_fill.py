import json
import logging
import pathlib

from pypdf import PdfReader, PdfWriter

from clients.openai_client import chat_json

logger = logging.getLogger(__name__)

# The 45 AcroForm field names in the ACRA CSP_Update PDF
KNOWN_PDF_FIELDS = [
    "Identification No", "Name", "Nationality", "Name_2",
    "Identification No_2", "Nationality_2", "BlockHouse Number",
    "Street Name", "Level", "Unit", "BuildingEstate Name",
    "Foreign Address Line 1", "Foreign Address Line 2",
    "BlockHouse Number_2", "Street Name_2", "Level_2", "Unit_2",
    "BuildingEstate Name_2", "Foreign Address Line 1_2",
    "Foreign Address Line 2_2", "Mobile Number", "Email Address",
    "Identification Type", "Date of Birth", "Date of Change of Name",
    "Date of Deed Poll", "Effective Date of Change",
    "Identification Type_2", "Effective Date of Change2",
    "Effective Date of Change3", "Postal Code",
    "Effective Date of Change 4", "Postal Code2",
    "Effective Date of Change 5", "Effective Date of Change 6",
    "Effective Date of Change 7", "Effective Date of Change of Category",
    "Effective Date of Change of Supporting Documents",
]

FIELD_MAPPING_PROMPT = """\
You are a compliance automation assistant. Given a list of extracted form field values \
and a list of PDF AcroForm field names, map the extracted values to the appropriate \
PDF fields.

Return a JSON object where keys are PDF field names and values are the strings to fill in. \
Only include fields that have a value to fill. If a field has no matching data, omit it.

PDF AcroForm field names:
{pdf_fields}

Extracted form data:
{form_data}
"""


async def map_fields_with_openai(form_fields: list[dict]) -> dict[str, str]:
    """Use OpenAI to map pipeline output fields to PDF AcroForm field names."""
    form_data = json.dumps(
        [{"field_id": f["field_id"], "value": f["value"], "description": f["description"]}
         for f in form_fields if f.get("value")],
        indent=2,
    )
    result = await chat_json(
        FIELD_MAPPING_PROMPT.format(
            pdf_fields=json.dumps(KNOWN_PDF_FIELDS),
            form_data=form_data,
        ),
        "Map the extracted values to PDF fields. Return only the JSON mapping.",
    )
    logger.info("OpenAI mapped %d PDF fields", len(result))
    return result


async def fill_pdf(pdf_path: str, form_fields: list[dict], output_path: str) -> str:
    """Fill the ACRA PDF AcroForm fields using pipeline output.

    Args:
        pdf_path: Path to the source PDF with AcroForm fields.
        form_fields: The 'fields' list from layer4 fill_form() output.
        output_path: Where to write the filled PDF.

    Returns:
        The output_path of the filled PDF.
    """
    reader = PdfReader(pdf_path)
    writer = PdfWriter(clone_from=pdf_path)

    # Get field mapping from OpenAI
    field_map = await map_fields_with_openai(form_fields)

    if not field_map:
        logger.warning("No fields mapped — writing unchanged PDF")
        pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            writer.write(f)
        return output_path

    # Fill fields — clone_from preserves AcroForm dict
    writer.update_page_form_field_values(writer.pages[0], field_map)

    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    logger.info("Filled PDF written to %s (%d fields)", output_path, len(field_map))
    return output_path
