import asyncio,json,urllib.request,base64
from pathlib import Path
import websockets
release=Path('/mnt/data/smartbox-deployments/20261025-kifu-rank-fallback-93f2038a0')
async def main():
 pages=json.load(urllib.request.urlopen('http://127.0.0.1:9222/json/list'));pages=[p for p in pages if p.get('type')=='page']
 assert len(pages)==1
 p=pages[0];original=json.loads((release/'pre-activation-browser.json').read_text())['url'];seq=0
 async with websockets.connect(p['webSocketDebuggerUrl'],max_size=16*1024*1024) as ws:
  async def call(method,params=None):
   nonlocal seq
   seq+=1;i=seq;await ws.send(json.dumps({'id':i,'method':method,'params':params or {}}))
   while True:
    obj=json.loads(await ws.recv())
    if obj.get('id')==i:
     if 'error' in obj:raise RuntimeError(obj['error'])
     return obj.get('result',{})
  async def ev(expression):
   r=await call('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True})
   if r.get('exceptionDetails'):raise RuntimeError(r['exceptionDetails'])
   return r.get('result',{}).get('value')
  async def screen(name):
   data=await call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
   (release/name).write_bytes(base64.b64decode(data['data']))
  async def settle():
   for _ in range(30):
    try:
     if await ev('document.readyState === "complete" && !!document.querySelector(".kiosk")'):
      await ev('document.fonts.ready.then(()=>true)');return
    except Exception:pass
    await asyncio.sleep(.3)
  await call('Page.reload',{'ignoreCache':True});await settle();await screen('browser-after-refresh.png')
  auth=await ev('(async()=>{const r=await fetch("/api/v1/auth/me");const j=await r.json();return {status:r.status,authenticated:r.ok};})()')
  result={'original_url':original,'auth_after_refresh':auth,'identity_restored':False}
  if auth['status']==401:
   clicked=await ev('(()=>{const b=[...document.querySelectorAll("button,a")].find(b=>b.textContent.includes("去盒子主页")||b.textContent.trim()==="主页");if(b){b.click();return true;}return false;})()')
   assert clicked,'expected normal launcher return button missing'
   for _ in range(40):
    await asyncio.sleep(.3)
    try:
     if await ev('!!document.querySelector("#tile-go")'):break
    except Exception:pass
   else:raise AssertionError('launcher Go tile not ready')
   launcher_auth=await ev('(async()=>{const r=await fetch("/api/auth/me");const j=await r.json();return {status:r.status,authenticated:r.ok};})()')
   result['launcher_auth']=launcher_auth;assert launcher_auth['status']==200,'launcher existing session unavailable'
   await ev('document.querySelector("#tile-go").click()')
   for _ in range(50):
    await asyncio.sleep(.3)
    try:
     if await ev('location.port === "8081" && !!document.querySelector(".kiosk")'):break
    except Exception:pass
   else:raise AssertionError('Go app did not reopen')
   await settle()
   auth=await ev('(async()=>{const r=await fetch("/api/v1/auth/me");const j=await r.json();return {status:r.status,authenticated:r.ok};})()')
   result['identity_restored']=auth['status']==200;assert auth['status']==200
   await call('Page.navigate',{'url':original});await settle()
  result['final_auth']=auth
  if '/kiosk/kifu' in original:
   for _ in range(40):
    if await ev('document.querySelectorAll(".record-match").length > 0'):break
    await asyncio.sleep(.25)
   await ev('document.fonts.ready.then(()=>true)')
   result['record_cards']=await ev('([...document.querySelectorAll(".record-match") ].slice(0,6).map(e=>({ranks:[...e.querySelectorAll(".record-match__rank")].map(x=>({text:x.textContent,font:getComputedStyle(x).fontSize})),result:e.querySelector(".record-match__result-label")?.textContent,center_delta:(()=>{const r=e.querySelector(".record-match__result").getBoundingClientRect(),n=e.querySelector(".record-match__name").getBoundingClientRect();return (r.top+r.bottom-n.top-n.bottom)/2;})()})))')
   result['list_source']=await ev('(async()=>{const r=await fetch(location.pathname.startsWith("/kiosk/kifu")?"/api/v1/kifu/albums?page=1&page_size=3&lang=cn":"/api/v1/user-games/?page=1&page_size=3&sort=created_at_desc");const d=await r.json();return {status:r.status,authority:d.authority,rows:(d.items??[]).map(x=>({id:x.id,black_rank:x.black_rank,white_rank:x.white_rank,display_black_rank:x.display_black_rank,display_white_rank:x.display_white_rank,black_origin:x.black_rank_origin,white_origin:x.white_rank_origin,source_id:x.black_rank_source?.source_ref?.source_item_id,result:x.result}))};})()')
  result['page']=await ev('({url:location.href,title:document.title,width:innerWidth,height:innerHeight,loaded_scripts:[...document.scripts].map(s=>s.src).filter(Boolean)})')
  assert result['page']['url']==original
  await screen('browser-after-restored.png')
  (release/'browser-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps(result,ensure_ascii=False,indent=2))
asyncio.run(main())
