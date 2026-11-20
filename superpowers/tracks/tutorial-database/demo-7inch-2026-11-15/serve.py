"""Loopback-only preview server with read-only OGS exercise caching."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import re
import urllib.request

HERE = Path(__file__).resolve().parent

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def do_GET(self):
        stream = re.fullmatch(r'/stream/(\d+)\.mp4', self.path)
        if stream:
            # The laptop serves one origin, as the real kiosk will in production.
            # Read only exact, public media URLs from this demo's fixed allowlist.
            try:
                manifest = json.loads((HERE / 'manifest.json').read_text())
                clip = next(c for c in manifest['clips'] if c['id'] == int(stream.group(1)))
                url = clip['profiles']['kiosk-7-v1']['url']
                if not url.startswith('https://go.sailorvoyage.top/media/tutorial_assets/'):
                    raise ValueError('Unexpected media origin')
                headers = {}
                requested = self.headers.get('Range')
                if requested:
                    if not re.fullmatch(r'bytes=\d*-\d*', requested):
                        return self.send_error(416)
                    headers['Range'] = requested
                upstream = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20)
                if not upstream.headers.get('Content-Type', '').startswith('video/'):
                    upstream.close()
                    raise ValueError('Upstream did not return video')
            except Exception:
                return self.send_error(503, 'Online video unavailable; use local demo backup')
            with upstream:
                self.send_response(upstream.status)
                for name in ['Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges']:
                    if upstream.headers.get(name):
                        self.send_header(name, upstream.headers[name])
                self.end_headers()
                try:
                    while chunk := upstream.read(65536):
                        self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    pass
            return
        video = re.fullmatch(r'/media-cache/(\d+)\.mp4', self.path)
        if video:
            path = HERE / 'media-cache' / (video.group(1) + '.mp4')
            if not path.exists():
                return self.send_error(404)
            size = path.stat().st_size
            start, end = 0, size - 1
            raw_range = self.headers.get('Range')
            match_range = re.fullmatch(r'bytes=(\d*)-(\d*)', raw_range or '')
            if raw_range and not match_range:
                return self.send_error(416)
            if match_range:
                lo, hi = match_range.groups()
                if lo:
                    start = int(lo)
                    end = min(int(hi), size - 1) if hi else size - 1
                elif hi:
                    start = max(0, size - int(hi))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.end_headers()
                    return
            self.send_response(206 if match_range else 200)
            self.send_header('Content-Type', 'video/mp4')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(end - start + 1))
            if match_range:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            with path.open('rb') as source:
                source.seek(start)
                remaining = end - start + 1
                try:
                    while remaining:
                        chunk = source.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            return
        match = re.fullmatch(r'/api/steps/(\d+)', self.path)
        if not match:
            return super().do_GET()
        page = int(match.group(1))
        if not 1 <= page <= 10000:
            return self.send_error(404)
        cache = HERE / 'steps' / f'{page}.json'
        try:
            if not cache.exists():
                url = f'https://modelstella.com/api/v1/tutorials/ogs-course/steps/{page}?lang=zh-cn&layout=kiosk19'
                with urllib.request.urlopen(url, timeout=12) as response:
                    payload = json.load(response)
                if payload['page'] != page:
                    raise ValueError('Unexpected page identity')
                cache.write_text(json.dumps(payload, ensure_ascii=False))
            payload = cache.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception:
            self.send_error(503, 'Exercise unavailable; retry when online')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18950)
    args = parser.parse_args()
    print(f'http://127.0.0.1:{args.port}/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
