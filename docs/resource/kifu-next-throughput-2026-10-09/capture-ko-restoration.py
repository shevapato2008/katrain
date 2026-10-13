"""Capture known Japanese reading URLs and two finite quoted conflict searches per owner."""

import concurrent.futures
import datetime
import gzip
import hashlib
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DIRECTORY = Path(__file__).parent
HEADERS = {'Accept-Encoding': 'identity', 'User-Agent': 'Mozilla/5.0'}


def write_gzip(path, value):
    path.write_bytes(gzip.compress(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                            separators=(',', ':')).encode(), mtime=0))


def capture(url, role, query=None):
    response = requests.get(url, params={'where': 'nexearch', 'query': query} if query else None,
                            headers=HEADERS, timeout=30)
    fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        body = response.content.decode('utf-8')
    except UnicodeDecodeError:
        body = response.content.decode('shift_jis')
    soup = BeautifulSoup(body, 'html.parser')
    for element in soup(['script', 'style']):
        element.decompose()
    visible = soup.get_text(' ', strip=True)
    main = soup.select_one('#main_pack')
    result_text = main.get_text(' ', strip=True) if main else visible
    data = {'url': response.url, 'http_status': response.status_code, 'fetched_at': fetched_at,
            'body_text': body, 'body_sha256': hashlib.sha256(body.encode()).hexdigest(),
            'body_excerpt': body, 'locator': 'Complete retained known-source HTTP response',
            'source_role': role, 'observed_lang': 'ko' if query else 'ja'}
    assert response.status_code == 200, (url, response.status_code)
    return data, visible, result_text


def script_variants(reading):
    yield reading
    yield ''.join(chr(ord(char) - 0x60) if '\u30a1' <= char <= '\u30f6' else char for char in reading)
    yield ''.join(chr(ord(char) + 0x60) if '\u3041' <= char <= '\u3096' else char for char in reading)


def process(target):
    role = ('official_person_page' if 'nihonkiin.or.jp' in target['reading_source_url']
            else 'biographical_dictionary' if 'kotobank.jp' in target['reading_source_url']
            else 'professional_go_rating_archive')
    profile, visible, _ = capture(target['reading_source_url'], role)
    compact = re.sub(r'\s+', '', visible)
    assert re.sub(r'\s+', '', target['original_name']) in compact
    reading = next((value for value in script_variants(target['archival_reading'])
                    if re.sub(r'\s+', '', value) in compact), None)
    assert reading is not None, (target['prod_id'], 'complete known kana absent')
    surname, given = reading.split()
    queries = []
    for key, value in (('original_go', target['original_name']), ('candidate_go', target['current_ko'])):
        query = f'"{value}" 바둑'
        captured, _, results = capture('https://search.naver.com/search.naver', 'search_results', query)
        captured['locator'] = 'Actual first Naver result page for this exact quoted name plus 바둑'
        queries.append({'role': key, 'query': query, 'capture': captured,
                        'visible_result_text': results,
                        'relevant_results': None, 'conclusion': 'pending_manual_conflict_review'})
    return {'target': target, 'profile_capture': profile,
            'reading': reading, 'surname': surname, 'given': given,
            'profile_visible_text': visible, 'queries': queries,
            'status': 'actual_sources_captured_pending_manual_conflict_review'}


def main():
    targets = json.loads((DIRECTORY / 'ko-restore-top20-targets.json').read_text())
    directory = DIRECTORY / 'fresh-known-source-captures'
    directory.mkdir(exist_ok=True)
    summary = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process, target): target for target in targets}
        for future in concurrent.futures.as_completed(futures):
            target = futures[future]
            try:
                data = future.result()
            except Exception as error:
                summary.append({'prod_id': target['prod_id'], 'status': 'source_capture_failed',
                                'error': str(error)})
                print(target['prod_id'], 'capture failed', type(error).__name__, flush=True)
                continue
            write_gzip(directory / f"{target['prod_id']}.json.gz", data)
            summary.append({'prod_id': target['prod_id'], 'status': 'captured',
                            'reading': data['reading'], 'display_name': target['current_ko'],
                            'source_url': data['profile_capture']['url'],
                            'source_body_sha256': data['profile_capture']['body_sha256']})
            print(target['prod_id'], data['reading'], 'profile + two real queries retained', flush=True)
    (DIRECTORY / 'fresh-capture-summary.json').write_text(
        json.dumps(sorted(summary, key=lambda item: item['prod_id']), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
