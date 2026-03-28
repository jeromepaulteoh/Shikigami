import json
import logging

from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


def _parse_json_response(raw: str) -> dict:
    """Parse JSON from OpenAI response, handling markdown fences."""
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines).strip()
    return json.loads(raw)


async def chat_json(system_prompt: str, user_content: str, model: str | None = None) -> dict:
    """Send a chat completion and parse the response as JSON."""
    client = _get_client()
    response = await client.chat.completions.create(
        model=model or OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    logger.debug("OpenAI raw response: %s", raw[:500])
    return _parse_json_response(raw)
