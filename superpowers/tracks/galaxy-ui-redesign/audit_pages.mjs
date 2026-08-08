import { chromium } from 'playwright';
const B='http://127.0.0.1:8901';
const R=[['dashboard','/galaxy'],['play-menu','/galaxy/play'],['play-ai-setup','/galaxy/play/ai'],
['play-human-lobby','/galaxy/play/human'],['research','/galaxy/research'],['report-list','/galaxy/report'],
['kifu','/galaxy/kifu'],['live','/galaxy/live'],['live-match-detail','/galaxy/live/yike_184016'],
['tsumego-levels','/galaxy/tsumego'],['tsumego-15k','/galaxy/tsumego/15k'],
['tsumego-problem','/galaxy/tsumego/problem/10039'],['tutorials','/galaxy/tutorials']];
const b=await chromium.launch(); const ctx=await b.newContext({viewport:{width:1440,height:900}});
const out=[];
for(const [name,path] of R){
  const p=await ctx.newPage();
  await p.goto(B+path,{waitUntil:'networkidle',timeout:25000}).catch(()=>{});
  await p.waitForTimeout(1600);
  const r=await p.evaluate(()=>{
    const SIDEBAR=240, vw=innerWidth;
    const cv=document.querySelector('canvas');
    const cb=cv?cv.getBoundingClientRect():null;
    // 右边栏：贴右边、够高、够宽的容器
    let rail=null,rw=0;
    for(const d of document.querySelectorAll('div')){const x=d.getBoundingClientRect();
      if(x.width>280&&x.width<900&&x.height>500&&x.right>vw-6&&x.top<200){if(x.width>rw){rw=x.width;rail=d;}}}
    // 棋盘正上方是否压着东西（在中列范围内、且在棋盘上边之上、有可见文字）
    let above=[];
    if(cb){for(const el of document.querySelectorAll('h1,h2,h3,h4,h5,h6,button,[role="button"],nav,a')){
      const x=el.getBoundingClientRect();
      if(x.height>0&&x.bottom<=cb.top+2&&x.left>=SIDEBAR-10&&x.right<=(rail?rail.getBoundingClientRect().left:vw)+10){
        const t=(el.innerText||'').replace(/\s+/g,' ').trim();
        if(t&&t.length<24)above.push(t);}}}
    const hs=[...document.querySelectorAll('button')].map(e=>Math.round(e.getBoundingClientRect().height)).filter(h=>h>0);
    return {board:cb?Math.round(cb.width):null, boardTop:cb?Math.round(cb.top):null,
      rail:Math.round(rw)||null, above:[...new Set(above)].slice(0,4),
      btnH:[...new Set(hs)].sort((a,b)=>a-b)};
  });
  out.push([name,r]); await p.close();
}
console.log('页面'.padEnd(20),'棋盘  右栏  棋盘上方压着的东西            按钮高度');
for(const [n,r] of out){
  console.log(n.padEnd(20), String(r.board??'—').padEnd(5), String(r.rail??'—').padEnd(5),
    (r.above.length?r.above.join(' / '):'—').padEnd(28), r.btnH.join(','));
}
await b.close();
