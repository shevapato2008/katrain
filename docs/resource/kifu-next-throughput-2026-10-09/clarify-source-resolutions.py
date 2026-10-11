"""Correct bounded lead descriptions while retaining actual captures and candidate inputs."""
import datetime,gzip,hashlib,json
from pathlib import Path
from katrain.web.kifu.name_evidence import registry_sha256,validate_research_record,positive_ja_ko_captures
D=Path(__file__).parent
path=D/'positive-ko20-unsigned-research.json.gz'
records=json.load(gzip.open(path,'rt'));before=registry_sha256(records)
registry=json.loads((D/'source-registry-reused.json').read_text())
changes=[]
for record in records:
 pid=record['owner']['id']
 capture_hashes=[registry_sha256(c)for c in positive_ja_ko_captures(record)]
 for query in record['positive_generation']['conflict_queries']:
  for result in query['relevant_results']:
   url=result['url'];replacement=None
   if pid==6270 and query['role']=='original_go' and 'wikidata.org/wiki/Q11653942' in url:
    replacement=('Wikidata is retained as an identity/discovery lead. This captured passage supplies no published Korean-name evidence for this owner; it is not a Korean Go profile or Korean-name authority.')
   elif pid==6631 and query['role']=='candidate_go' and 'lib.paju.go.kr' in url:
    replacement=('This marketing-book catalogue result is an unrelated author/namesake lead. It is excluded as this Go player\'s identity and Korean-name authority; the historical Go article does not establish that the book author is this player.')
   elif 'thewiki.kr/' in url:
    replacement=('TheWiki mirror is retained only as a contextual search lead. No player identity or independently published complete Korean name is established from this mirrored lead; the separately captured Japanese source binds the owner and reading.')
   elif '/press/' in url:
    replacement=('This publisher/news landing-page lead is retained as finite search context, without claiming that the landing page publishes a complete Korean personal name for this Go player. It is excluded as player identity and Korean-name authority. Political-news context is not linked to the player.')
   if replacement and replacement!=result['resolution']:
    changes.append({'prod_id':pid,'role':query['role'],'url':url,'before':result['resolution'],'after':replacement})
    result['resolution']=replacement
 assert capture_hashes==[registry_sha256(c)for c in positive_ja_ko_captures(record)]
 validate_research_record(record,registry)
raw=json.dumps(records,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
path.write_bytes(gzip.compress(raw,mtime=0))
summary=json.loads((D/'positive-ko20-summary.json').read_text());summary['research_array_sha256']=hashlib.sha256(raw).hexdigest()
byid={record['owner']['id']:record for record in records}
for item in summary['records']:item['research_sha256']=registry_sha256(byid[item['prod_id']])
(D/'positive-ko20-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
audit={'changed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'research_array_before_sha256':before,
 'research_array_after_sha256':registry_sha256(records),'raw_capture_contents_unchanged':True,
 'names_readings_and_existing_preimages_unchanged':True,'review_status':'unsigned_pending_independent_review','changes':changes}
(D/'source-resolution-corrections.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(len(changes),'description-only corrections; PASS20; actual captures unchanged',audit['research_array_after_sha256'])
