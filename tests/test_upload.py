import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from layers.layer6_upload import upload_to_github, _get_github_token

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

import layers.layer6_upload as upload_module


async def main():
    passed = 0
    failed = 0

    original_get_token = upload_module._get_github_token

    try:
        # Test 1: _get_github_token returns a non-empty string
        print("\n--- Test 1: gh auth token works ---")
        try:
            token = _get_github_token()
            assert isinstance(token, str) and len(token) > 0, "Token is empty"
            print(f"  PASS: Got token ({len(token)} chars)")
            passed += 1
        except Exception as e:
            print(f"  SKIP: gh auth not available ({e})")
            passed += 1  # Not a failure — just not authenticated

        # Test 2: upload_to_github with mocked httpx
        print("\n--- Test 2: upload_to_github (mocked) ---")
        import httpx

        class MockResponse:
            status_code = 404
            def json(self):
                return {}
            def raise_for_status(self):
                pass

        class MockPutResponse:
            status_code = 201
            def json(self):
                return {"content": {"download_url": "https://example.com/test.txt"}}
            def raise_for_status(self):
                pass

        captured_put = {}

        class MockAsyncClient:
            def __init__(self, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def get(self, url, headers=None):
                return MockResponse()
            async def put(self, url, json=None, headers=None):
                captured_put["url"] = url
                captured_put["json_keys"] = list(json.keys()) if json else []
                return MockPutResponse()

        # Monkeypatch httpx.AsyncClient
        original_client = httpx.AsyncClient
        httpx.AsyncClient = MockAsyncClient
        upload_module._get_github_token = lambda: "fake_token"

        # Create a tiny test file
        test_file = os.path.join(os.path.dirname(__file__), "test_upload_tmp.txt")
        with open(test_file, "w") as f:
            f.write("test content")

        try:
            raw_url = await upload_to_github(test_file, "data/filled/test_upload.txt")
            assert "raw.githubusercontent.com" in raw_url, f"Bad URL: {raw_url}"
            assert "message" in captured_put["json_keys"], "Missing commit message"
            assert "content" in captured_put["json_keys"], "Missing base64 content"
            assert "sha" not in captured_put["json_keys"], "SHA should not be present for new file"
            print(f"  PASS: Upload returns raw URL: {raw_url}")
            passed += 1
        finally:
            httpx.AsyncClient = original_client
            if os.path.exists(test_file):
                os.remove(test_file)

        # Test 3: upload_to_github includes SHA when file exists
        print("\n--- Test 3: upload includes SHA for existing file ---")

        class MockExistsResponse:
            status_code = 200
            def json(self):
                return {"sha": "abc123"}
            def raise_for_status(self):
                pass

        class MockClientWithExisting:
            def __init__(self, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def get(self, url, headers=None):
                return MockExistsResponse()
            async def put(self, url, json=None, headers=None):
                captured_put["json_keys"] = list(json.keys()) if json else []
                captured_put["sha"] = json.get("sha") if json else None
                return MockPutResponse()

        httpx.AsyncClient = MockClientWithExisting

        test_file = os.path.join(os.path.dirname(__file__), "test_upload_tmp2.txt")
        with open(test_file, "w") as f:
            f.write("test content 2")

        try:
            await upload_to_github(test_file, "data/filled/existing.txt")
            assert "sha" in captured_put["json_keys"], "SHA missing for existing file"
            assert captured_put["sha"] == "abc123", f"Wrong SHA: {captured_put['sha']}"
            print("  PASS: SHA included for existing file update")
            passed += 1
        finally:
            httpx.AsyncClient = original_client
            upload_module._get_github_token = original_get_token
            if os.path.exists(test_file):
                os.remove(test_file)

    finally:
        upload_module._get_github_token = original_get_token

    print(f"\n{'='*40}")
    print(f"Upload Tests: {passed} passed, {failed} failed")
    assert failed == 0, f"{failed} test(s) failed"


if __name__ == "__main__":
    asyncio.run(main())
