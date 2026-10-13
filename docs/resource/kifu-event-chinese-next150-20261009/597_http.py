import json,time
from urllib.parse import urlencode
from urllib.request import urlopen
groups=[{'raw_value': '16届GG拍卖杯绅士淑女擂台10局', 'core_key': 'GG拍卖杯绅士淑女擂台', 'raw_parts': [{'kind': 'edition', 'text': '16届'}, {'kind': 'core', 'text': 'GG拍卖杯绅士淑女擂台'}, {'kind': 'game', 'text': '10局'}], 'names': {'cn': '16届GG拍卖杯绅士淑女擂台10局', 'tw': '第16屆GG拍賣杯紳士淑女擂臺第10局', 'jp': '第16回GGオークション杯紳士淑女勝ち抜き 第10局', 'ko': '제16회 GG경매배 신사숙녀 연승 제10국', 'en': '16th GG Auction Cup Gentlemen and Ladies Relay, Game 10'}, 'current_games': 1, 'scope_sha256': {'TEST': '2c4060997e015da8b6209b2a0ec369739b3984d5603ae27343c0eac9c6041d98', 'PROD': '2c4060997e015da8b6209b2a0ec369739b3984d5603ae27343c0eac9c6041d98'}, 'owner_id': {'TEST': 52108, 'PROD': 52108}}, {'raw_value': '韩国第27期国手战循环圈第20局', 'core_key': '韩国第27期国手战循环圈', 'raw_parts': [{'kind': 'core', 'text': '韩国第27期国手战循环圈'}, {'kind': 'game', 'text': '第20局'}], 'names': {'cn': '韩国第27期国手战循环圈第20局', 'tw': '韓國第27期國手戰循環圈第20局', 'jp': '韓国第27期国手戦リーグ 第20局', 'ko': '한국 제27기 국수전 리그 제20국', 'en': 'Korea Kuksu Tournament, Term 27 Round Robin, Game 20'}, 'current_games': 2, 'scope_sha256': {'TEST': '19d5350d8a8542a97a872d2bd42d67a0c907ec5f30db0c188a92eff4c724d89c', 'PROD': '19d5350d8a8542a97a872d2bd42d67a0c907ec5f30db0c188a92eff4c724d89c'}, 'owner_id': {'TEST': 100090, 'PROD': 100090}}]
result=[]
for group in groups:
 baseline=None
 for lang in ('cn','tw','jp','ko','en','ru'):
  query=group['names']['en' if lang=='ru' else lang];start=time.monotonic()
  with urlopen('http://127.0.0.1:8001/api/v1/kifu/albums?'+urlencode({'lang':lang,'q':query,'page_size':20}),timeout=40) as response:data=json.load(response)
  assert data['total']>0 and data['items']
  assert all(row['display_event']==query for row in data['items']), (lang,query,[row.get('display_event') for row in data['items']])
  current=(data['total'],[row['id'] for row in data['items']])
  if baseline is None:baseline=current
  else:assert current==baseline,(lang,query,current,baseline)
  result.append({'language':lang,'query':query,'total':data['total'],'checked_cards':len(data['items']),'elapsed_ms':round((time.monotonic()-start)*1000)})
print(json.dumps({'passed':True,'cases':len(result),'results':result},ensure_ascii=False))
