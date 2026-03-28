import logging

from clients.tinyfish import TinyFishClient

logger = logging.getLogger(__name__)

AUTOFILL_GOAL_TEMPLATE = """\
You are an automation agent filling out a BizFile+ general lodgement form.

Complete the following steps on the form page:

1. In the "Email address" field, type: {email}
2. In the "Description of lodgement" textarea, type exactly: {description}
3. In the "Date of document" field, clear any existing value and type: {date}
4. For the "Attach form" upload zone, download the PDF from this URL: {pdf_url}
   Then upload it using the file input in the attach form section.
5. Click the "Review and confirm" button.

IMPORTANT:
- Do NOT click Submit on the review page. Stop after reaching the review page.
- The description field has a 200 character limit — do not exceed it.
- Wait for each field to be filled before moving to the next.
"""


def build_autofill_goal(
    form_output: dict,
    pdf_url: str,
    email: str = "jerometeoh@gmail.com",
    date: str = "28 Mar 2026",
) -> str:
    """Construct a concrete TinyFish goal from pipeline output.

    Args:
        form_output: The full output dict from fill_form() (layer4).
        pdf_url: GitHub raw URL for the filled PDF.
        email: Email address to fill in the form.
        date: Date of document value.

    Returns:
        A natural-language goal string for TinyFish.
    """
    # Extract lodgement description from the form output
    description = ""
    for field in form_output.get("fields", []):
        if field["field_id"] == "lodgement_description" and field.get("value"):
            value = field["value"]
            description = value if isinstance(value, str) else str(value)
            break

    if not description:
        description = "Withdrawal from Being Approved Liquidators"

    # Truncate to 200 chars for the BizFile+ field limit
    description = description[:200]

    goal = AUTOFILL_GOAL_TEMPLATE.format(
        email=email,
        description=description,
        date=date,
        pdf_url=pdf_url,
    )

    logger.info("Built autofill goal (%d chars)", len(goal))
    return goal


async def run_autofill(form_url: str, form_output: dict, pdf_url: str) -> dict:
    """Run the TinyFish agent to fill the mock BizFile+ portal.

    Args:
        form_url: URL of the locally-served form.html (e.g. http://localhost:8080/form.html).
        form_output: The full output dict from fill_form() (layer4).
        pdf_url: GitHub raw URL for the filled PDF.

    Returns:
        TinyFish result dict.
    """
    goal = build_autofill_goal(form_output, pdf_url)
    client = TinyFishClient()
    result = await client.run_single(url=form_url, goal=goal, browser_profile="stealth")

    if result.get("error"):
        logger.error("TinyFish autofill failed: %s", result)
    else:
        logger.info("TinyFish autofill completed successfully")

    return result
