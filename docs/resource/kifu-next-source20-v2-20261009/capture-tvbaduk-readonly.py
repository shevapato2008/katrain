"""Save public TV Baduk pages for source research; no database access."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import requests
from bs4 import BeautifulSoup

D = Path(__file__).parent
BASE = 'https://www.tvbaduk.com/info/'
WANTED = {
    '천루이': 6366, '황량위': 6547, '차오스야오': 3820,
    '자오젠난': 368, '왕보강': 5473, '황진쉬안': 6552,
    '선징': 5349, '왕예훙이': 5468, '자오쯔지': 5952,
    '판시위': 5790, '천더룽': 6322, '황번': 6550,
    '친쓰웨': 5675, '천야펑': 6296, '장자야오': 4634,
    '쉬젠잉': 5890, '양원카이': 5133,
}

def capture_index(nation):
    url = BASE + f'gisa_info.asp?S_nation={nation}'
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    raw = response.content
    path = D / f'tvbaduk-nation{nation}-index.body'
    path.write_bytes(raw)
    soup = BeautifulSoup(raw, 'html.parser')
    names = {}
    for a in soup.find_all('a', href=True):
        match = re.fullmatch(r"javascript:view\('([^']+)'\)", a['href'])
        if match:
            names[a.get_text(strip=True)] = match.group(1)
    return {'url': url, 'final_url': response.url, 'http_status': response.status_code,
            'fetched_at': datetime.now(timezone.utc).isoformat(), 'body_file': path.name,
            'body_bytes': len(raw), 'body_sha256': sha256(raw).hexdigest()}, names

def capture_profile(item):
    name, player_id, code, nation = item
    url = BASE + 'gisa_view.asp'
    data = {'S_nation': nation, 'S_ob_forc': '', 'S_sort_mode': 'A', 'prpl_code': code}
    response = requests.post(url, data=data, timeout=30)
    response.raise_for_status()
    raw = response.content
    path = D / f'tvbaduk-{player_id}.body'
    path.write_bytes(raw)
    soup = BeautifulSoup(raw, 'html.parser')
    content = soup.get_text(' ', strip=True)
    i = content.find('소속 :')
    excerpt = content[i:i+150] if i >= 0 else content[:150]
    return {'prod_player_id': player_id, 'name_in_index': name, 'prpl_code': code,
            'url': url, 'method': 'POST', 'post_data': data, 'final_url': response.url,
            'http_status': response.status_code, 'fetched_at': datetime.now(timezone.utc).isoformat(),
            'body_file': path.name, 'body_bytes': len(raw), 'body_sha256': sha256(raw).hexdigest(),
            'visible_profile_excerpt': excerpt}

index, names = capture_index('2')
tw_index, tw_names = capture_index('4')
items = []
for name, player_id in WANTED.items():
    assert name in names, name
    items.append((name, player_id, names[name], '2'))
assert tw_names['천창칭'] == '20000086'
items.append(('천창칭', 6378, tw_names['천창칭'], '4'))
with ThreadPoolExecutor(max_workers=4) as pool:
    rows = [f.result() for f in as_completed(pool.submit(capture_profile, item) for item in items)]
rows.sort(key=lambda r: r['prod_player_id'])
(D / 'tvbaduk-captures.json').write_text(json.dumps({'china_index': index, 'taiwan_index': tw_index, 'profiles': rows}, ensure_ascii=False, indent=2) + '\n')
for row in rows:
    print(row['prod_player_id'], row['name_in_index'], row['visible_profile_excerpt'])
