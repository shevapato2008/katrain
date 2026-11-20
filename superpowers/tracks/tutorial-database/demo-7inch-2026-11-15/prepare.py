"""Prepare an isolated, real-content laptop Demo; never writes a remote API."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BATCH = ROOT / 'data/tutorial_media_batches/ogs-book-sources-20261113'
API = 'https://modelstella.com/api/v1/tutorials/ogs-course'
MEDIA = 'https://go.sailorvoyage.top/media/'

# Curated examples, not an assertion that every first-three-chapter lesson has video.
CLIPS = {
    4275: '认识棋盘的九个区域', 4276: '一路线到四路线',
    4278: '一颗棋子的四口气', 4289: '连接成块后，一起数气',
    4310: '只剩一口气，就是打吃', 4341: '堵住最后一口气，再提子',
    4372: '被打吃后，怎样逃出', 4401: '找出被打吃的棋子',
    4440: '寻找解救棋块的出路', 4441: '先看一条走不通的路',
    4442: '选择能够解救棋块的出路',
    4453: '打吃，要从哪个方向', 4454: '方向不对，会发生什么',
    4455: '再比较另一侧的打吃',
    4863: '认识征子的连续追赶', 4864: '顺着征子读下去',
}
PLAYLISTS = {
    'rules-intro': [4275, 4278, 4341], 'the-board': [4275, 4276],
    'count-liberties': [4278, 4289], 'count_chains': [4289],
    'in_atari': [4310], 'count-atari': [4401],
    'capture_stone': [4341], 'capture_chain': [4341],
    'escape': [4372], 'find_escape': [4440, 4441, 4442],
    'create_opening': [4440, 4441, 4442],
    'atari-to-side': [4453, 4454, 4455],
    'atari-to-stones': [4453, 4454, 4455], 'ladder': [4863, 4864],
}

def get_json(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)

def main():
    (HERE / 'media-cache').mkdir(exist_ok=True)
    (HERE / 'steps').mkdir(exist_ok=True)
    (HERE / 'posters').mkdir(exist_ok=True)
    (HERE / 'assets').mkdir(exist_ok=True)
    shell = ROOT / 'katrain/web/ui/src/kiosk-shell'
    shutil.copyfile(shell / 'fonts.css', HERE / 'assets/fonts.css')
    if not (HERE / 'assets/fonts').exists():
        (HERE / 'assets/fonts').symlink_to(shell / 'fonts', target_is_directory=True)
    if not (HERE / 'assets/stones').exists():
        (HERE / 'assets/stones').symlink_to(ROOT / 'katrain/web/ui/src/assets/tutorial-stones', target_is_directory=True)
    course = get_json(API + '?lang=zh-cn')
    course['chapters'] = [c for c in course['chapters'] if c['number'] <= 3]
    chapter_ids = {c['id'] for c in course['chapters']}
    course['lessons'] = [l for l in course['lessons'] if l['chapter_id'] in chapter_ids]
    (HERE / 'course.json').write_text(json.dumps(course, ensure_ascii=False))
    snapshot = json.loads((BATCH / 'snapshot.json').read_text())
    figures = {r['figure']['id']: (b, r['figure']) for b in snapshot['books'] for r in b['figures']}
    current = json.loads((BATCH / 'tasks-latest.json').read_text())['current']

    def clip(fid):
        book, f = figures[fid]
        live = current[str(fid)]
        assert live['pronunciation_current'] and len(live['profiles']) == 2, f'Not current dual media: {fid}'
        result = {'id': fid, 'title': CLIPS[fid], 'page': f['page'], 'catalog_id': book['catalog_id'],
                  'book': '《曹薰铉和李昌镐围棋教室：入门篇·' + ('上卷》' if book['book_id'] == 11 else '下卷》'),
                  'source_text': f.get('book_text', ''), 'profiles': {}}
        for name, key in live['profiles'].items():
            url = MEDIA + key
            with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=20) as response:
                size = int(response.headers['Content-Length'])
            result['profiles'][name] = {'url': url, 'asset': key, 'bytes': size}
        dst = HERE / 'media-cache' / f'{fid}.mp4'
        expected = result['profiles']['kiosk-7-v1']['bytes']
        if not dst.exists() or dst.stat().st_size != expected:
            urllib.request.urlretrieve(result['profiles']['kiosk-7-v1']['url'], dst)
        result['profiles']['kiosk-7-v1']['sha256'] = hashlib.sha256(dst.read_bytes()).hexdigest()
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=width,height', '-of', 'json', str(dst)], capture_output=True, text=True, check=True)
        info = json.loads(probe.stdout)
        assert any(s.get('width') == 1024 and s.get('height') == 600 for s in info['streams'])
        result['duration'] = float(info['format']['duration'])
        poster = HERE / 'posters' / f'{fid}.jpg'
        if not poster.exists():
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(min(6, result['duration']/3)), '-i', str(dst), '-frames:v', '1', '-vf', 'scale=640:-1', '-q:v', '3', str(poster)], check=True)
        print(fid, f['page'], expected, flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        clips = list(pool.map(clip, CLIPS))
    lessons_by_id = {l['id']: l for l in course['lessons']}
    # Warm real first exercises plus the two main demo lessons for offline use.
    pages = {lessons_by_id[l]['first_page'] for l in PLAYLISTS}
    for lid in ['count-liberties', 'capture_stone']:
        l = lessons_by_id[lid]
        pages.update(range(l['first_page'], l['first_page'] + l['step_count']))
    def step(page):
        d = get_json(API + f'/steps/{page}?lang=zh-cn&layout=kiosk19')
        assert d['page'] == page
        (HERE / 'steps' / f'{page}.json').write_text(json.dumps(d, ensure_ascii=False))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(step, sorted(pages)))
    manifest = {'prototype_only': True, 'video_origin': 'TEST / home-ubuntu', 'exercise_origin': API,
                'screen': {'width': 1024, 'height': 600, 'inches': 7}, 'clips': clips, 'playlists': PLAYLISTS,
                'kiosk_bytes': sum(c['profiles']['kiosk-7-v1']['bytes'] for c in clips),
                'galaxy_bytes': sum(c['profiles']['galaxy-4k-v1']['bytes'] for c in clips)}
    (HERE / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print('ready', len(clips), 'clips;', len(PLAYLISTS), 'video lessons;', len(pages), 'cached real exercises')

if __name__ == '__main__':
    main()
