import base64
import logging
import subprocess

import httpx

from config import GITHUB_REPO

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _get_github_token() -> str:
    """Get GitHub token from gh CLI."""
    result = subprocess.run(
        ["gh", "auth", "token"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


async def upload_to_github(
    file_path: str,
    repo_path: str = "data/filled/CSP_Update_filled.pdf",
) -> str:
    """Upload a file to GitHub via the Contents API.

    Args:
        file_path: Local file to upload.
        repo_path: Path within the repo to upload to.

    Returns:
        The raw.githubusercontent.com URL for the uploaded file.
    """
    token = _get_github_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    with open(file_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{repo_path}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Check if file exists (need SHA for update)
        sha = None
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            sha = resp.json().get("sha")

        body = {
            "message": f"Upload filled PDF: {repo_path}",
            "content": content_b64,
        }
        if sha:
            body["sha"] = sha

        resp = await client.put(url, json=body, headers=headers)
        resp.raise_for_status()

    raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{repo_path}"
    logger.info("Uploaded to GitHub: %s", raw_url)
    return raw_url
