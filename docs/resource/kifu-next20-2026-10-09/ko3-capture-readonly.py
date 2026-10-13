"""Retain three published Japanese readings and six bounded conflict result pages."""

import datetime
import gzip
import hashlib
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup


D = Path(__file__).parent
TARGETS = [
    (5396, "浜中隆光", "ハマナカ タカミツ", "하마나카 다카미쓰",
     "https://www.nihonkiin.or.jp/player/htm/ki000173.html",
     "https://www.igorating.com/players/takamitsu-hamanaka"),
    (4276, "奥村靖", "オクムラ ヤスシ", "오쿠무라 야스시",
     "https://www.nihonkiin.or.jp/player/htm/ki000240.htm",
     "https://igorating.com/players/yasushi-okumura"),
    (4782, "明戸和巳", "アケド カズミ", "아케도 가즈미",
     "https://archive.nihonkiin.or.jp/player/htm/ki000129.htm",
     "https://www.igorating.com/players/kazumi-akedo"),
]


def fetch(url, role, query=None):
    for attempt in range(2):
        try:
            response = requests.get(
                url,
                params={"where": "nexearch", "query": query} if query else None,
                headers={"Accept-Encoding": "identity", "User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            break
        except requests.exceptions.ChunkedEncodingError:
            if attempt:
                raise
    response.raise_for_status()
    body = response.content.decode("utf-8")
    return {
        "url": response.url,
        "http_status": response.status_code,
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "body_text": body,
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "body_excerpt": body,
        "locator": "Complete actual HTTP response; visible name and reading checked in source body",
        "source_role": role,
        "observed_lang": "ko" if query else "ja",
    }


def compact_visible(capture):
    soup = BeautifulSoup(capture["body_text"], "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    return re.sub(r"\s+", "", soup.get_text(" ", strip=True))


def main():
    rows = []
    for player_id, original, reading, candidate, official_url, igo_url in TARGETS:
        official = fetch(official_url, "official_person_page")
        igo = fetch(igo_url, "professional_go_rating_archive")
        for source in (official, igo):
            visible = compact_visible(source)
            assert original in visible, (player_id, "original absent", source["url"])
            assert reading.replace(" ", "") in visible or reading.translate(
                str.maketrans({chr(k): chr(k - 0x60) for k in range(0x30A1, 0x30F7)})
            ).replace(" ", "") in visible, (player_id, "full reading absent", source["url"])
        assert original in igo["body_text"], (player_id, "compact original absent from Igo raw")
        queries = []
        for role, name in (("original_go", original), ("candidate_go", candidate)):
            query = f'"{name}" 바둑'
            capture = fetch("https://search.naver.com/search.naver", "search_results", query)
            queries.append({"role": role, "query": query, "capture": capture})
        rows.append({"player_id": player_id, "original_name": original, "reading": reading,
                     "candidate_name": candidate, "official_profile": official, "igo_profile": igo,
                     "queries": queries})
        print(player_id, "official + compact Igo + 2 Naver pages captured", flush=True)
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    (D / "ko3-actual-source-captures.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    print("capture sha256", hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
