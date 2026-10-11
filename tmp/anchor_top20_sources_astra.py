import concurrent.futures,datetime,hashlib,json,sys
from pathlib import Path
import bs4,requests
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/resource/kifu-player-exact-anchor-top20-independent-sources-astra-2026-10-04'
OUT.mkdir(exist_ok=True)
SOURCES={
 'nihon-kudo':'https://www.nihonkiin.or.jp/player/htm/ki000026.html',
 'nihon-nakaonoda':'https://www.nihonkiin.or.jp/player/htm/ki000217.html',
 'nihon-tsuruta':'https://www.nihonkiin.or.jp/player/htm/ki000433.html',
 'nihon-yao':'https://www.nihonkiin.or.jp/player/htm/ki000447.html',
 'nihon-okuda':'https://www.nihonkiin.or.jp/player/htm/ki000400.html',
 'nihon-yokotsuka':'https://www.nihonkiin.or.jp/player/htm/ki000462.html',
 'nihon-cho':'https://www.nihonkiin.or.jp/player/htm/ki000187.html',
 'kansai-taniguchi':'https://kansaikiin.jp/kisi_prof/taniguchitoru.html',
 'kansai-tsuji':'https://kansaikiin.jp/kisi_prof/tsujishigehito.html',
 'kansai-tanaka':'https://kansaikiin.jp/kisi_prof/tanakakoyu.html',
 'kansai-kubo':'https://kansaikiin.jp/kisi_prof/kubokatsuaki.html',
 'kba-han-seungju':'https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000744',
 'kba-hwang-jaeyeon':'https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000686',
 'kba-ha-chanseok':'https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000022',
 'kba-han-jongjin':'https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000109',
 'cwa-zhangtao':'https://wqapi.cwql.org.cn/playerInfo/CWA000126',
 'cwa-zhouheyang':'https://wqapi.cwql.org.cn/playerInfo/CWA000014',
 'cwa-chenyichun':'https://wqapi.cwql.org.cn/playerInfo/CWA000670',
 'wiki-zhangtao':'https://zh.wikipedia.org/wiki/张涛_(围棋棋手)',
 'wiki-zhouheyang':'https://zh.wikipedia.org/wiki/周鹤洋',
 'wiki-murashima':'https://ja.wikipedia.org/wiki/村島誼紀',
 'cwa-roster':'https://wqapi.cwql.org.cn/playerInfo/professional/list',
}
def save(item):
 key,url=item
 meta=OUT/(key+'.meta.json')
 if meta.exists():return json.loads(meta.read_text())
 r=requests.get(url,timeout=35);r.raise_for_status()
 isjson='json' in r.headers.get('content-type','')
 r.encoding='utf-8' if isjson else r.apparent_encoding
 rawpath=OUT/(key+('.json' if isjson else '.html'));rawpath.write_bytes(r.content)
 if isjson:content=json.dumps(r.json(),ensure_ascii=False,sort_keys=True,indent=2)
 else:
  soup=bs4.BeautifulSoup(r.text,'html.parser')
  for s in soup(['script','style']):s.decompose()
  content='\n'.join(line.strip() for line in soup.get_text('\n').splitlines() if line.strip())
 textpath=OUT/(key+'.txt');textpath.write_text(content)
 info={'key':key,'url':url,'resolved_url':r.url,'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':r.status_code,
       'raw_path':str(rawpath.relative_to(ROOT)),'raw_sha256':hashlib.sha256(r.content).hexdigest(),
       'text_path':str(textpath.relative_to(ROOT)),'text_sha256':hashlib.sha256(textpath.read_bytes()).hexdigest()}
 meta.write_text(json.dumps(info,ensure_ascii=False,sort_keys=True,indent=2))
 return info
if __name__=='__main__':
 selected={k:v for k,v in SOURCES.items() if len(sys.argv)==1 or k in sys.argv[1:]}
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
  future={pool.submit(save,item):item[0] for item in selected.items()}
  for f in concurrent.futures.as_completed(future):
   try:r=f.result();print(r['key'],r['status'],r['raw_sha256'],flush=True)
   except Exception as e:print(future[f],type(e).__name__,flush=True)
