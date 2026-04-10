# Fix Video Seek Bar (HTTP Range Request Support) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make tutorial video progress bars seekable by adding HTTP Range request support to the asset serving endpoint.

**Architecture:** Starlette 0.36.3's `FileResponse` does not handle `Range` headers. When a browser `<video>` element tries to seek, it sends `Range: bytes=N-M` but gets back a full 200 response, so seeking silently fails. We add a helper function that parses the `Range` header and returns a `Response` with status 206 + `Content-Range`, falling back to `FileResponse` with `Accept-Ranges: bytes` for non-range requests. Single file change.

**Tech Stack:** FastAPI, Starlette, Python

---

### Task 1: Add Range Request Support to Asset Endpoint

**Files:**
- Modify: `katrain/web/api/v1/endpoints/tutorials.py:1-14,258-264`
- Test: `tests/web_ui/test_tutorial_db_api.py`

- [ ] **Step 1: Write the failing test for Range requests**

Add to `tests/web_ui/test_tutorial_db_api.py`:

```python
def test_video_asset_range_request(client, tmp_path, monkeypatch):
    """Asset endpoint returns 206 Partial Content for Range requests."""
    import katrain.web.api.v1.endpoints.tutorials as tut_mod

    # Create a fake video file
    asset_dir = tmp_path / "tutorial_assets" / "test" / "video"
    asset_dir.mkdir(parents=True)
    video_file = asset_dir / "fig_1.mp4"
    video_file.write_bytes(b"x" * 1000)

    monkeypatch.setattr(tut_mod, "ASSET_BASE", tmp_path)

    # Range request for first 100 bytes
    resp = client.get(
        "/api/v1/tutorials/assets/tutorial_assets/test/video/fig_1.mp4",
        headers={"Range": "bytes=0-99"},
    )
    assert resp.status_code == 206
    assert resp.headers["content-range"] == "bytes 0-99/1000"
    assert resp.headers["accept-ranges"] == "bytes"
    assert len(resp.content) == 100


def test_video_asset_range_request_open_ended(client, tmp_path, monkeypatch):
    """Asset endpoint handles open-ended Range (bytes=500-)."""
    import katrain.web.api.v1.endpoints.tutorials as tut_mod

    asset_dir = tmp_path / "tutorial_assets" / "test" / "video"
    asset_dir.mkdir(parents=True)
    video_file = asset_dir / "fig_1.mp4"
    video_file.write_bytes(b"x" * 1000)

    monkeypatch.setattr(tut_mod, "ASSET_BASE", tmp_path)

    resp = client.get(
        "/api/v1/tutorials/assets/tutorial_assets/test/video/fig_1.mp4",
        headers={"Range": "bytes=500-"},
    )
    assert resp.status_code == 206
    assert resp.headers["content-range"] == "bytes 500-999/1000"
    assert len(resp.content) == 500


def test_asset_without_range_has_accept_ranges(client, tmp_path, monkeypatch):
    """Non-range requests still include Accept-Ranges header."""
    import katrain.web.api.v1.endpoints.tutorials as tut_mod

    asset_dir = tmp_path / "tutorial_assets" / "test" / "video"
    asset_dir.mkdir(parents=True)
    video_file = asset_dir / "fig_1.mp4"
    video_file.write_bytes(b"x" * 100)

    monkeypatch.setattr(tut_mod, "ASSET_BASE", tmp_path)

    resp = client.get(
        "/api/v1/tutorials/assets/tutorial_assets/test/video/fig_1.mp4",
    )
    assert resp.status_code == 200
    assert resp.headers["accept-ranges"] == "bytes"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `CI=true uv run pytest tests/web_ui/test_tutorial_db_api.py::test_video_asset_range_request tests/web_ui/test_tutorial_db_api.py::test_video_asset_range_request_open_ended tests/web_ui/test_tutorial_db_api.py::test_asset_without_range_has_accept_ranges -v`

Expected: FAIL — current endpoint returns 200 for Range requests and no `Accept-Ranges` header.

- [ ] **Step 3: Implement Range request handling**

Edit `katrain/web/api/v1/endpoints/tutorials.py`:

**Add imports** (line 11, after the existing FastAPI imports):

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
```

(Add `Request` to the existing fastapi import, and `Response` to the existing responses import.)

**Replace the `get_asset` endpoint** (lines 258-264) with:

```python
@router.get("/assets/{asset_path:path}")
async def get_asset(asset_path: str, request: Request):
    """Serve a tutorial asset with HTTP Range support for video seeking."""
    file_path = _safe_asset_path(asset_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")

    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")

    if range_header and range_header.startswith("bytes="):
        # Parse "bytes=start-end" or "bytes=start-"
        range_spec = range_header[6:]
        parts = range_spec.split("-", 1)
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        with open(file_path, "rb") as f:
            f.seek(start)
            data = f.read(length)

        import mimetypes

        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        return Response(
            content=data,
            status_code=206,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Content-Type": content_type,
            },
        )

    return FileResponse(file_path, headers={"Accept-Ranges": "bytes"})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `CI=true uv run pytest tests/web_ui/test_tutorial_db_api.py -v`

Expected: ALL PASS (including existing `test_path_traversal_rejected`).

- [ ] **Step 5: Manual verification with curl**

Start server if not running: `python -m katrain --ui web --port 8001 &`

```bash
# Find a real video file
VIDEO=$(ls data/tutorial_assets/*/video/fig_*.mp4 2>/dev/null | head -1)
ASSET_PATH=${VIDEO#data/}

# Test Range request
curl -s -o /dev/null -w "%{http_code}" -H "Range: bytes=0-1023" http://localhost:8001/api/v1/tutorials/assets/$ASSET_PATH
# Expected: 206

# Test full request has Accept-Ranges
curl -sI http://localhost:8001/api/v1/tutorials/assets/$ASSET_PATH | grep -i accept-ranges
# Expected: accept-ranges: bytes
```

- [ ] **Step 6: Browser verification**

Open a tutorial figure page with video in browser. Verify:
1. Video plays normally
2. Progress bar can be dragged/seeked to any position
3. Clicking on the progress bar jumps to that position
4. Pause still works

- [ ] **Step 7: Commit**

```bash
git add katrain/web/api/v1/endpoints/tutorials.py tests/web_ui/test_tutorial_db_api.py
git commit -m "fix(backend): add HTTP Range support to asset endpoint for video seeking"
```

---

## Root Cause Summary

| Layer | Status | Detail |
|-------|--------|--------|
| FFmpeg encoding | OK | Final per-figure videos have `-movflags +faststart` (line 731). Section concat also has it (line 1060). Moov atom is at the beginning. |
| Frontend `<video>` | OK | Uses native `controls` attribute — browser handles seek UI correctly. |
| **Backend serving** | **BUG** | `FileResponse` (Starlette 0.36.3) ignores `Range` headers. Returns full file with 200. Browser cannot seek without 206 Partial Content support. |
