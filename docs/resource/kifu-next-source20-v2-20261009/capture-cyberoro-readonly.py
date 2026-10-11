"""Save public GET profile pages that use TV Baduk's player codes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import requests

D = Path(__file__).parent
selected = {368, 3820, 4634, 5133, 5473, 5675, 5790, 6296, 6378, 6547}
tv = json.loads((D / 'tvbaduk-captures.json').read_text())

def get(row):
    pid = row['prod_player_id']
    nation = row['post_data']['S_nation']
    code = row['prpl_code']
    url = f'https://www.cyberoro.com/info/N_player_view.oro?prpl_code={code}&Tdiv=&Sdiv=&S_nation={nation}'
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    raw = response.content
    path = D / f'cyberoro-{pid}.body'
    path.write_bytes(raw)
    return {'prod_player_id': pid, 'url': url, 'method': 'GET', 'http_status': response.status_code,
            'final_url': response.url, 'fetched_at': datetime.now(timezone.utc).isoformat(),
            'body_file': path.name, 'body_bytes': len(raw), 'body_sha256': sha256(raw).hexdigest(),
            'prpl_code': code, 'same_player_code_as_tvbaduk': True}

with ThreadPoolExecutor(max_workers=4) as pool:
    rows = [f.result() for f in as_completed(pool.submit(get, row) for row in tv['profiles'] if row['prod_player_id'] in selected)]
rows.sort(key=lambda row: row['prod_player_id'])
assert len(rows) == len(selected)
(D / 'cyberoro-captures.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
print('saved', len(rows))
