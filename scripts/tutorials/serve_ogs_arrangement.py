"""Loopback TEST preview; serves an isolated build and read-only OGS endpoints."""

import argparse
import hashlib
import json
import mimetypes
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--review-html", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18957)
    args = parser.parse_args()
    dist = args.dist.resolve()
    data_dir = args.data_dir.resolve()
    review = args.review_html.resolve()
    for required in (dist / "index.html", data_dir / "test-manifest.json", review):
        if not required.is_file():
            parser.error(f"missing preview artifact: {required}")

    # These are actual TEST DB exports, not fixture exercises. Refuse mismatched snapshots.
    receipt = json.loads((data_dir / "test-ogs-snapshot-receipt.json").read_text())
    if (
        receipt.get("identity", {}).get("system_identifier") != "7596941912817897507"
        or receipt.get("environment") != "test"
        or receipt.get("book_id") != 80
        or receipt.get("snapshot_is_simulated") is not False
    ):
        parser.error("expected the pinned real TEST book80 snapshot")
    snapshots = {}
    for kind in ("course", "steps"):
        raw = (data_dir / f"test-{kind}.zh-cn.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != receipt[f"{kind}_sha256"]:
            parser.error(f"TEST {kind} snapshot checksum mismatch")
        snapshots[kind] = json.loads(raw)
    if len(snapshots["steps"]) != 3551:
        parser.error("expected 3551 real TEST steps")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from katrain.web.content.board_variants import adapt_ogs_step

    manifest = json.loads((data_dir / "test-manifest.json").read_text())
    media = {
        f'/preview-media/{clip["id"]}/{profile}.mp4': details["url"]
        for clip in manifest["clips"]
        for profile, details in clip["profiles"].items()
    }
    if any(
        not re.fullmatch(
            r"https://go\.sailorvoyage\.top/media/tutorial_assets/[a-z0-9-]+/media/[0-9a-f]{32}/video-2d-(?:galaxy-4k-v1|kiosk-7-v1)\.mp4",
            url,
        )
        for url in media.values()
    ):
        parser.error("media must come from the pinned TEST manifest")

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, content, content_type="application/json; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(content)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            request = urlsplit(self.path)
            path = request.path
            if path == "/health":
                return self.reply(
                    200,
                    b'{"environment":"TEST","read_only":true,"exercise_source":"pinned_real_TEST_snapshot","live_public_reader_deployed":false}',
                )
            if path in media and not request.query:
                requested = self.headers.get("Range", "bytes=0-")
                if not re.fullmatch(r"bytes=(?:[0-9]+-[0-9]*|-[0-9]+)", requested):
                    return self.reply(416, b'{"detail":"invalid media range"}')
                try:
                    response = urlopen(Request(media[path], headers={"Range": requested}), timeout=20)
                except (HTTPError, URLError, TimeoutError):
                    return self.reply(503, b'{"detail":"TEST video unavailable; retry"}')
                with response:
                    if not response.headers.get("Content-Type", "").startswith("video/"):
                        return self.reply(503, b'{"detail":"TEST video unavailable; retry"}')
                    self.send_response(response.status)
                    for header in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                        if response.headers.get(header):
                            self.send_header(header, response.headers[header])
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    if self.command != "HEAD":
                        try:
                            while chunk := response.read(65536):
                                self.wfile.write(chunk)
                        except (BrokenPipeError, ConnectionResetError, TimeoutError):
                            pass
                return
            if path.startswith("/api/"):
                if not re.fullmatch(r"/api/v1/tutorials/ogs-course(?:/steps/[1-9][0-9]{0,3})?", path):
                    return self.reply(404, b'{"detail":"TEST preview exposes only OGS reads"}')
                query = parse_qs(request.query, keep_blank_values=True)
                if set(query) - {"lang", "board_variant"} or any(len(v) != 1 for v in query.values()):
                    return self.reply(400, b'{"detail":"unsupported query"}')
                language = query.get("lang", ["zh-cn"])[0]
                variant = query.get("board_variant", [None])[0]
                if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2,4})?", language) or variant not in (None, "kiosk19"):
                    return self.reply(400, b'{"detail":"unsupported language or board variant"}')
                if language != "zh-cn":
                    return self.reply(404, b'{"detail":"This TEST snapshot preview is zh-cn only"}')
                if path.endswith("/ogs-course"):
                    payload = snapshots["course"]
                else:
                    payload = snapshots["steps"].get(path.rsplit("/", 1)[1])
                    if payload is None:
                        return self.reply(404, b'{"detail":"TEST step not found"}')
                    if variant:
                        payload = adapt_ogs_step(payload)
                return self.reply(200, json.dumps(payload, ensure_ascii=False).encode())
            if path == "/arrangement/test-manifest.json":
                return self.reply(200, (data_dir / "test-manifest.json").read_bytes())
            exports = {"/" + review.with_suffix(ext).name: review.with_suffix(ext) for ext in (".json", ".csv")}
            if path in exports:
                content_type = (
                    "application/json; charset=utf-8" if path.endswith(".json") else "text/csv; charset=utf-8"
                )
                return self.reply(200, exports[path].read_bytes(), content_type)
            if path in ("/review", "/review.html"):
                return self.reply(200, review.read_bytes(), "text/html; charset=utf-8")
            if path in ("/go-curriculum.html", "/ogs-video-outline-2026-11-12.html"):
                return self.reply(200, (review.parent / path.lstrip("/")).read_bytes(), "text/html; charset=utf-8")
            if "%" in path or "\\" in path or ".." in path.split("/"):
                return self.reply(400, b'{"detail":"invalid path"}')
            target = (dist / path.lstrip("/")).resolve()
            if not target.is_relative_to(dist):
                return self.reply(404, b'{"detail":"not found"}')
            if not target.is_file():
                if path == "/" or path.startswith("/kiosk/"):
                    target = dist / "index.html"
                else:
                    return self.reply(404, b'{"detail":"not found"}')
            return self.reply(
                200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            )

        def do_POST(self):
            self.reply(405, b'{"detail":"read-only TEST preview"}')

        do_PUT = do_POST
        do_PATCH = do_POST
        do_DELETE = do_POST

    print(f"TEST player: http://127.0.0.1:{args.port}/kiosk/tutorial", flush=True)
    print(f"Review table: http://127.0.0.1:{args.port}/review", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
