"""Bounded read-only engine experiment; no app/database/payment calls or cache clears."""
import concurrent.futures
import hashlib
import json
import math
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent
SOURCE = json.loads((BASE / 'input.json').read_text())
START = time.monotonic()
DEADLINE = START + 240
ROWS = []
PREFIX = 'membership-cost-20261101-' + str(int(time.time()))

def health(port):
    data = json.load(urllib.request.urlopen('http://127.0.0.1:%d/health' % port, timeout=8))
    name = data['default_model']
    m = data['models'][name]
    return {'port': port, 'name': name, 'sha256': m['model_sha256'],
            'verified': m.get('model_sha256_verified'), 'ready': data.get('ready')}

HEALTH = {p: health(p) for p in (8000, 8002)}
assert all(m['verified'] and m['ready'] for m in HEALTH.values())

def query(port, turn, visits=500, ownership=True, label='serial'):
    if time.monotonic() >= DEADLINE:
        raise TimeoutError('experiment deadline reached before submission')
    request_id = '%s-%s-%d-%d-%d' % (PREFIX, label, port, turn, visits)
    payload = {'id': request_id, 'rules': SOURCE['rules'], 'komi': SOURCE['komi'],
               'boardXSize': 19, 'boardYSize': 19, 'initialStones': SOURCE['initial_stones'],
               'initialPlayer': SOURCE['initial_player'], 'moves': SOURCE['moves'][:turn],
               'analyzeTurns': [turn], 'maxVisits': visits, 'includeOwnership': ownership,
               'includePolicy': False, 'priority': -100,
               'overrideSettings': {'reportAnalysisWinratesAs': 'BLACK'}}
    before = time.monotonic()
    request = urllib.request.Request('http://127.0.0.1:%d/analyze' % port,
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=40) as response:
        result = json.load(response)
    elapsed = time.monotonic()-before
    wrapper, root = result.get('_wrapper', {}), result.get('rootInfo', {})
    assert not result.get('error'), result.get('error')
    assert result.get('id') == request_id and result.get('turnNumber') == turn
    assert result.get('isDuringSearch') is False and root.get('visits', 0) >= visits
    assert wrapper.get('model_sha256') == HEALTH[port]['sha256']
    assert wrapper.get('model_sha256_verified') is True
    if ownership:
        assert len(result.get('ownership', [])) == 361
    row = {'phase': label, 'port': port, 'turn': turn, 'requested_visits': visits,
           'root_visits': root['visits'], 'ownership': ownership, 'wall_seconds': elapsed,
           'model': wrapper.get('selected_model'), 'model_sha256': wrapper.get('model_sha256')}
    ROWS.append(row)
    return row

def run_phase(label, jobs, concurrency=1):
    before = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        pending = [pool.submit(query, p, turn, visits, own, label) for p,turn,visits,own in jobs]
        results = [f.result() for f in pending]
    elapsed = time.monotonic()-before
    summary = {'phase': label, 'count': len(results), 'concurrency': concurrency,
               'wall_seconds': elapsed, 'positions_per_second': len(results)/elapsed,
               'root_visits_per_second': sum(r['root_visits'] for r in results)/elapsed,
               'latency_mean_seconds': statistics.mean(r['wall_seconds'] for r in results),
               'latency_median_seconds': statistics.median(r['wall_seconds'] for r in results),
               'latency_max_seconds': max(r['wall_seconds'] for r in results)}
    print(json.dumps(summary), flush=True)
    return summary

summaries = []
try:
    # Two low-priority warmup queries are recorded, excluded from pricing phases.
    for port in (8000, 8002):
        query(port, 7, label='warmup')
    for port in (8000,8002):
        summaries.append(run_phase('serial-500-%d' % port,
            [(port,t,500,True) for t in (18,46,73,101,129,157,184,201)]))
    # Production supports several reports concurrently; use distinct positions,
    # keep total client concurrency at three, and never clear shared engine cache.
    summaries.append(run_phase('parallel3-500-8002',
        [(8002,t,500,True) for t in range(23,204,8)], 3))
    summaries.append(run_phase('parallel3-500-8000',
        [(8000,t,500,True) for t in range(25,204,8)], 3))
    summaries.append(run_phase('territory-200-8002',
        [(8002,t,200,True) for t in (36,83,137,193)]))
    summaries.append(run_phase('deep-2000-8002',
        [(8002,t,2000,True) for t in (42,113,171)]))
    summaries.append(run_phase('hint-only-500-8002',
        [(8002,t,500,False) for t in (32,91,149,199)]))
    status = 'complete'
except Exception as exc:
    status = '%s: %s' % (type(exc).__name__, str(exc))
finally:
    output = {'format':'membership-engine-benchmark-v1', 'status':status,
        'source':{k:v for k,v in SOURCE.items() if k not in ('moves','initial_stones')},
        'source_moves':len(SOURCE['moves']), 'health':HEALTH,
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'started_unix':int(time.time()-(time.monotonic()-START)),
        'total_wall_seconds':time.monotonic()-START,
        'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,utilization.gpu,memory.used','--format=csv,noheader'],text=True).strip(),
        'summaries':summaries,'rows':ROWS,
        'limitations':['Warm ready engines; no cache clear; distinct positions within one attributed public game.',
                      'One V100 shared by both engine containers; concurrency groups run sequentially.',
                      'HTTP engine timing only, excludes business DB/report serialization/upload/queue.',
                      'root visits are search work units, not physical GPU neural inference counts.',
                      'low priority -100; no service restart or configuration change.']}
    (BASE/'result.json').write_text(json.dumps(output,indent=2))
    print(json.dumps({'status':status,'total_wall_seconds':output['total_wall_seconds'],'rows':len(ROWS)}),flush=True)
