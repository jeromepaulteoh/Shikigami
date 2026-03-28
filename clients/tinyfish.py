import asyncio
import json
import logging

import httpx

from config import TINYFISH_API_KEY

logger = logging.getLogger(__name__)

BASE_URL = "https://agent.tinyfish.ai/v1"

# API reference: https://docs.tinyfish.ai/api-reference
# Auth: X-API-Key header
# Endpoints used:
#   POST /v1/automation/run-sse   — SSE stream (STARTED, PROGRESS, COMPLETE, HEARTBEAT)
#   POST /v1/automation/run-batch — submit up to 100 runs, returns {run_ids: [...]}
#   GET  /v1/runs/{id}            — poll run status (PENDING|RUNNING|COMPLETED|FAILED|CANCELLED)


class TinyFishClient:

    POLL_INTERVAL = 5    # seconds between polls
    POLL_TIMEOUT = 300   # max seconds to wait for batch completion

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or TINYFISH_API_KEY
        self._headers = {
            "X-API-Key": self._api_key,
            "Content-Type": "application/json",
        }

    def _build_payload(self, url: str, goal: str, browser_profile: str = "stealth") -> dict:
        payload = {"url": url, "goal": goal}
        if browser_profile in ("lite", "stealth"):
            payload["browser_profile"] = browser_profile
        return payload

    # ── SSE (single) ─────────────────────────────────────────────

    async def run_single(
        self, url: str, goal: str, browser_profile: str = "stealth"
    ) -> dict:
        """Run a single extraction via SSE. Returns the result dict on COMPLETE."""
        payload = self._build_payload(url, goal, browser_profile)
        timeout = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", f"{BASE_URL}/automation/run-sse",
                    json=payload, headers=self._headers
                ) as response:
                    response.raise_for_status()
                    return await self._parse_sse_stream(response, url)
        except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
            logger.error("run_single failed for %s: %s", url, e)
            return {"error": "failed", "url": url}

    async def _parse_sse_stream(self, response: httpx.Response, url: str) -> dict:
        """Parse SSE events, return result from COMPLETE event."""
        async for line in response.aiter_lines():
            line = line.strip()
            if not line or line.startswith(":"):
                continue
            if line.startswith("data: "):
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type", "")
                if event_type == "PROGRESS":
                    logger.info("[%s] %s", event.get("run_id", "")[:8], event.get("purpose", ""))
                elif event_type == "COMPLETE":
                    if event.get("status") == "COMPLETED":
                        return event.get("result", {})
                    else:
                        logger.error("Task failed for %s: %s", url, event.get("error"))
                        return {"error": "failed", "url": url}

        # Stream ended without COMPLETE
        return {"error": "failed", "url": url}

    # ── Batch (run-batch + polling) ──────────────────────────────

    async def run_batch(
        self, tasks: list[dict]
    ) -> list[dict]:
        """Submit tasks via /run-batch, poll /runs/{id} until all complete."""
        payloads = [
            self._build_payload(
                t["url"], t["goal"], t.get("browser_profile", "stealth")
            )
            for t in tasks
        ]
        timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            # Submit batch
            resp = await client.post(
                f"{BASE_URL}/automation/run-batch",
                json={"runs": payloads},
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("error"):
                logger.error("Batch submission failed: %s", data["error"])
                return [{"error": "failed", "url": t["url"]} for t in tasks]

            run_ids = data.get("run_ids", [])
            if len(run_ids) != len(tasks):
                logger.error("run_ids count mismatch: got %d, expected %d", len(run_ids), len(tasks))
                return [{"error": "failed", "url": t["url"]} for t in tasks]

            # Poll until all complete
            return await self._poll_all(client, run_ids, tasks)

    async def _poll_all(
        self, client: httpx.AsyncClient, run_ids: list[str], tasks: list[dict]
    ) -> list[dict]:
        """Poll GET /v1/runs/{id} for each run until done or timeout."""
        results: dict[int, dict] = {}
        pending = set(range(len(run_ids)))
        elapsed = 0

        while pending and elapsed < self.POLL_TIMEOUT:
            await asyncio.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL

            for i in list(pending):
                try:
                    resp = await client.get(
                        f"{BASE_URL}/runs/{run_ids[i]}",
                        headers=self._headers,
                    )
                    resp.raise_for_status()
                    run_data = resp.json()
                    status = run_data.get("status", "")

                    if status == "COMPLETED":
                        results[i] = run_data.get("result", {})
                        pending.discard(i)
                    elif status in ("FAILED", "CANCELLED"):
                        results[i] = {"error": "failed", "url": tasks[i]["url"]}
                        pending.discard(i)
                    # PENDING / RUNNING — keep polling
                except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
                    logger.warning("Poll error for run %s: %s", run_ids[i], e)

        # Timeout: mark remaining as failed
        for i in pending:
            results[i] = {"error": "failed", "url": tasks[i]["url"]}

        return [results[i] for i in range(len(run_ids))]
