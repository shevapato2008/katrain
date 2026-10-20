from pathlib import Path
from collections import Counter
import json
from katrain.cron import config
from katrain.kifu_ingest.sync import check_production_identities
root=Path('/app/data/kifu_ingest')
m=json.loads((root/'packages/91315699-0f64c2b366a0d9ba.json').read_text())
instructions={}
for g in m['games']:
 for slot,ident in g.get('identities',{}).items():
  if not isinstance(ident,dict):continue
  kind='event' if slot=='event' else 'player'
  raw=g['metadata']['event' if slot=='event' else 'player_'+slot]
  key=(kind,raw,ident['canonical_name'])
  instructions[key]={'kind':kind,'raw':raw,'canonical_name':ident['canonical_name'],'name_decision':False}
request={'operation':'check-identities','game_count':len(m['games']),'instructions':list(instructions.values())}
r=check_production_identities(request,host=config.KIFU_INGEST_SSH_HOST,key_path=config.KIFU_INGEST_SSH_KEY,known_hosts=config.KIFU_INGEST_KNOWN_HOSTS,timeout=180)
assert set(r['results'])=={'qualified'},Counter(r['results'])
output={'status':'passed','request_sha256':r['request_sha256'],'games':len(m['games']),'instructions':len(instructions),'results':dict(Counter(r['results'])),'llm_calls':0,'scope':'actual restricted TEST-cron to PROD receiver readonly operation'}
(root/'e23-production-identity-probe.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output))
