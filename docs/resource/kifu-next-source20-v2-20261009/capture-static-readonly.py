"""Retain public GET response bodies underlying selected source pages."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import requests

D = Path(__file__).parent
URLS = {
 '5094-kowiki': 'https://ko.wikipedia.org/w/index.php?title=%EB%A6%AC%EA%B0%95&oldid=36505438',
 '5351-pairgo': 'https://www.pairgo.or.jp/amateur/26th/worldstudents/index_e.htm',
 '5351-sina': 'https://blog.sina.com.cn/s/blog_53a2e03d0102wg73.html',
 '4340-kansai': 'https://kansaikiin.jp/kisi_prof/andohinata.html',
 '4041-igo': 'https://www.igorating.com/players/ryo-maeda',
 '3844-zhtw-wiki': 'https://zh.wikipedia.org/zh-hant/%E7%AC%AC%E5%9B%9B%E5%B1%86%E4%B8%96%E7%95%8C%E6%99%BA%E5%8A%9B%E7%B2%BE%E8%8B%B1%E8%BF%90%E5%8A%A8%E6%9C%83',
 '339-jstart': 'https://jstart.co.kr/bbs/board.php?bo_table=news&page=3&wr_id=342',
}
def get(item):
 id, url = item
 response = requests.get(url, timeout=30)
 raw = response.content
 path = D / (id + '.body')
 if response.ok:
  path.write_bytes(raw)
 return {'id': id, 'url': url, 'method': 'GET', 'http_status': response.status_code,
         'final_url': response.url, 'fetched_at': datetime.now(timezone.utc).isoformat(),
         'body_file': path.name if response.ok else None, 'body_bytes': len(raw),
         'body_sha256': sha256(raw).hexdigest(), 'content_type': response.headers.get('Content-Type')}
with ThreadPoolExecutor(max_workers=4) as pool:
 rows = [f.result() for f in as_completed(pool.submit(get, x) for x in URLS.items())]
rows.sort(key=lambda x:x['id'])
(D / 'static-captures.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
for x in rows:print(x['id'],x['http_status'],x['body_bytes'])
