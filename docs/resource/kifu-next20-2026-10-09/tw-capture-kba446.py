"""Capture already identified KBA person page once; no identity search."""
import datetime,gzip,hashlib,json,re,urllib.request
from pathlib import Path
D=Path(__file__).parent
url='https://www.baduk.or.kr/record/player_view.asp?pkey=10001264'
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30)as r:
 raw=r.read();status=r.status;encoding=r.headers.get_content_charset()or'utf-8'
body=raw.decode(encoding);assert status==200 and '李貞垠'in body and 'foreignKey=10001264'in body
match=re.search(r'<p\b[^>]*>.*?이정은.*?</p\s*>',body,re.I|re.S);assert match
excerpt=body[max(0,match.start()-180):match.end()+380]
source={'url':url,'http_status':status,'fetched_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'raw_response_sha256':hashlib.sha256(raw).hexdigest(),'body_encoding':encoding,'body_text':body,'body_excerpt':excerpt,'identity_basis':'KBA own person pkey10001264 publishes complete 이정은(李貞垠) pair, DOB2007-08-21 and stable same-person diary link. Existing conventional CN/JP/KO owner evidence references this same official identity. Compatibility U+F9E1 retained exactly; TW target is generated official Hanja preservation, with no Taiwanese publication claim.','language_basis':'html_lang','observed_lang':'ko','tier':'official','source_role':'official_person_page','record_locator':'pkey=10001264'}
(D/'tw-kba446-raw-response.body.gz').write_bytes(gzip.compress(raw,mtime=0));(D/'tw-kba446-actual-capture.json.gz').write_bytes(gzip.compress(json.dumps(source,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(),mtime=0))
print('KBA446',source['fetched_at'],source['body_sha256'],excerpt[:180])
