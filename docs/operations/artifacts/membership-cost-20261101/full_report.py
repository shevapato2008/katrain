"""One public 305-move mainline, all 306 positions, serial report-shaped queries."""
import hashlib
import json
import math
import statistics
import time
import urllib.request
from pathlib import Path

base = Path(__file__).parent
game = json.loads((base/'report-input.json').read_text())
started_unix, started = time.time(), time.monotonic()
deadline = started+1200
health = json.load(urllib.request.urlopen('http://127.0.0.1:8002/health',timeout=8))
name = health['default_model']
model = health['models'][name]
assert health['ready'] and model['model_sha256_verified'] and name=='tf3-b11c768'
rows = []
status = 'running'
prefix = 'membership-full-report-%d-' % int(started_unix)

def persist():
    result={'format':'membership-complete-sequence-benchmark-v1', 'status':status,
            'started_unix':started_unix,'wall_seconds':time.monotonic()-started,
            'source':{k:v for k,v in game.items() if k not in ('moves','initial_stones')},
            'moves':len(game['moves']), 'expected_positions':len(game['moves'])+1,
            'completed_positions':len(rows), 'model':name,'model_sha256':model['model_sha256'],
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'concurrency':1, 'requested_visits':500,'ownership':True,'policy':False,
            'priority':-100,'rows':rows,
            'limitations':['Engine HTTP sequence, not an application report task; no report DB writes or billing.',
                           'Warm engine and persistent NN cache; a single public game is not a workload SLA.',
                           'Sequence follows current report worker 0..N, one request at a time.']}
    if rows:
        result['mean_request_seconds']=statistics.mean(r['seconds'] for r in rows)
        result['median_request_seconds']=statistics.median(r['seconds'] for r in rows)
    (base/'full-report-result.json').write_text(json.dumps(result,indent=2))
    return result

try:
    for turn in range(len(game['moves'])+1):
        if time.monotonic()>deadline: raise TimeoutError('20 minute experiment submission deadline')
        rid=prefix+str(turn)
        payload={'id':rid,'moves':game['moves'][:turn], 'initialStones':game['initial_stones'],
                 'initialPlayer':game['initial_player'],'rules':game['rules'],'komi':game['komi'],
                 'boardXSize':19,'boardYSize':19,'analyzeTurns':[turn], 'maxVisits':500,
                 'includeOwnership':True,'includePolicy':False,'priority':-100,
                 'overrideSettings':{'reportAnalysisWinratesAs':'BLACK'}}
        before=time.monotonic()
        request=urllib.request.Request('http://127.0.0.1:8002/analyze', data=json.dumps(payload).encode(),
                                       headers={'Content-Type':'application/json'})
        result=json.load(urllib.request.urlopen(request,timeout=40))
        elapsed=time.monotonic()-before
        assert not result.get('error') and result.get('id')==rid and result.get('turnNumber')==turn
        assert result.get('isDuringSearch') is False and result['rootInfo']['visits']>=500
        assert result['_wrapper'].get('model_sha256')==model['model_sha256']
        assert result['_wrapper'].get('model_sha256_verified') is True
        ownership=result.get('ownership',[])
        assert len(ownership)==361 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in ownership)
        assert result.get('moveInfos') and all(isinstance(m.get('move'),str) for m in result['moveInfos'])
        rows.append({'turn':turn,'seconds':elapsed,'root_visits':result['rootInfo']['visits']})
        persist()
        if turn%25==0:
            print(json.dumps({'completed':len(rows),'total':len(game['moves'])+1,
                              'wall_seconds':time.monotonic()-started,'last_seconds':elapsed}),flush=True)
    status='complete'
except Exception as exc:
    status=type(exc).__name__+': '+str(exc)
finally:
    result=persist()
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','source')}),flush=True)
