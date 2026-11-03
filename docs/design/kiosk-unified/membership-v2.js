/* Isolated, in-memory design fixture. No API, payment, storage, device or GPU calls. */
(() => {
  'use strict';
  const families = window.KioskDesignFamilies = window.KioskDesignFamilies || {};
  const params = new URLSearchParams(location.search);
  const epoch = Date.parse('2026-11-01T04:00:00Z');
  const start = performance.now();
  const now = () => epoch + performance.now() - start;
  const planCodes = ['plus', 'pro', 'max'];
  const catalog = {
    free:{name:'Free', reports:[1,1], interactive:[0,0]},
    plus:{name:'Plus', amount:29, reports:[1,7], interactive:[10,70], reference:'0.0967'},
    pro:{name:'Pro', amount:99, reports:[5,35], interactive:[50,350], reference:'0.066'},
    max:{name:'Max', amount:299, reports:[20,140], interactive:[200,1400], reference:'0.0498'},
    analysis_100_v1:{name:'100 次标准分析包',amount:29,credits:1000},
  };
  const scenarios = [['pro','Pro 会员'],['free','Free 周报告'],['exhausted','额度耗尽'],['not-started','24h 未开始'],['reserved','正在预留'],['offline','离线旧数据'],['boundary','跨零待重取'],['loading','加载中'],['error','同步失败']];
  const initialScenario = scenarios.some(([id])=>id===params.get('membership-state')) ? params.get('membership-state') : 'pro';
  const state = {scenario:initialScenario, currentPlan:initialScenario==='free'?'free':'pro', resource:'reports', balance:1000, order:null, seq:0, message:null, lastSync:epoch, boundaryAt:now()+3000, boundaryReceived:false, returnFocus:null, currentEndsAt:Date.parse('2026-12-01T04:00:00Z'), futureTerms:[], preservedFreeUse:false};
  let timer;
  let poll;
  const numeric = text => `<span class="kiosk-plex-num">${text}</span>`;
  const paths = {
    back:'<path d="m15 4-8 8 8 8M7 12h15"/>',
    close:'<path d="m6 6 12 12M18 6 6 18"/>',
    info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
    test:'<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><path d="M14 14h3v3h3v3h-6z"/>',
  };
  const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name]}</svg>`;
  const button = (label, attrs='', primary=false) => `<button type="button" ${primary?'class="mem-primary"':''} ${attrs}>${label}</button>`;
  const isMembership = id => id?.startsWith('membership-');
  const refresh = () => window.KioskMembershipRefresh?.();
  function go(id) { if(location.hash==='#'+id)refresh();else location.hash=id; }
  const free = () => state.currentPlan==='free';
  const plan = () => catalog[state.currentPlan];
  const online = () => state.scenario!=='offline';
  const accountReady = () => !['loading','error'].includes(state.scenario);
  const formatDate = value => new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value));
  const formatClock = value => new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(value));
  const formatDay = value => new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));
  function countdown(at) {
    const seconds = Math.max(0,Math.ceil((at-now())/1000));
    if(!seconds)return '正在核对额度';
    const days=Math.floor(seconds/86400), hours=Math.floor(seconds%86400/3600), minutes=Math.floor(seconds%3600/60), remain=seconds%60;
    return `${days?days+'天 ':''}${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}:${String(remain).padStart(2,'0')} 后恢复`;
  }
  function windowData(period) {
    const index=period==='h24'?0:1, limits=plan()[state.resource];
    let used=state.resource==='reports'?(index?8:1):(index?12:2);
    let reserved=state.resource==='reports'?1:0;
    if(free()){used=1;reserved=0;}
    if(state.preservedFreeUse){used=state.resource==='reports'?1:0;reserved=0;}
    if(state.scenario==='not-started'){used=0;reserved=0;}
    if(state.scenario==='exhausted'){used=limits[index];reserved=0;}
    if(state.scenario==='reserved'){reserved=state.resource==='reports'?2:4;used=index?(state.resource==='reports'?8:12):1;}
    const limit=limits[index], remaining=Math.max(0,limit-used-reserved);
    const reset=state.scenario==='boundary'&&period==='h24'&&!state.boundaryReceived?state.boundaryAt:Date.parse(index?'2026-11-01T16:00:00Z':'2026-11-02T02:00:00Z');
    return {limit,used,reserved,remaining,reset,percent:limit?Math.round(remaining/limit*1000)/10:null};
  }
  function usageWindow(period) {
    const data=windowData(period), unit=state.resource==='reports'?'份':'次';
    const notStarted=period==='h24'&&state.scenario==='not-started';
    return `<article class="mem-limit" aria-label="${period==='h24'?'24小时':'本周'}${state.resource==='reports'?'复盘报告':'标准分析'}剩余"><strong class="mem-limit-title">${period==='h24'?numeric('24')+' 小时':'本周'}</strong><div class="mem-limit-quantity"><b>${numeric(data.remaining)}</b> / ${numeric(data.limit)} ${unit} · ${numeric(data.percent)}%</div><div class="mem-progress" role="progressbar" aria-label="剩余比例" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${data.percent}"><i style="width:${data.percent}%"></i></div><div class="mem-limit-reset"><span ${notStarted?'':`data-mem-countdown="${data.reset}"`}>${notStarted?'首次使用后起计':numeric(countdown(data.reset))}</span><time>${notStarted?'未开始计时':formatDate(data.reset)+' 北京时间'}</time></div>${data.reserved?`<div class="mem-reserved">已预留 ${numeric(data.reserved)} ${unit}，完成后计入使用</div>`:''}</article>`;
  }
  function syncLabel() {
    if(state.scenario==='loading')return '<div class="mem-sync is-stale"><span>等待同步 · 尚未确认</span></div>';
    const stale=!online()||state.scenario==='error';
    return `<div class="mem-sync ${stale?'is-stale':''}"><i class="mem-status-dot"></i><span>${stale?'数据待刷新':'已同步'} · <time data-mem-sync>${formatClock(state.lastSync)}</time></span></div>`;
  }
  function account() {
    const loading=!accountReady(),next=state.futureTerms[0];
    const nextLabel=next?'下期 '+catalog[next.code].name+' · '+formatDay(next.startsAt).slice(5)+' 生效':'同账号在网页与盒子共用';
    return `<aside class="mem-aside"><div class="mem-account"><strong>${loading?'待同步':plan().name}</strong><span class="mem-badge">${loading?'读取中':'当前权益'}</span></div><p>${loading?'正在确认云端账号权益':free()?'每自然周 1 份普通报告<br>不赠独立互动额度':`有效至 ${numeric(formatDay(state.currentEndsAt))}<br>${nextLabel}${state.futureTerms.length>1?'<br>另有 '+(state.futureTerms.length-1)+' 期已排定':''}`}</p><div class="mem-wallet"><span>已购余额</span><strong>${loading?'—':numeric(state.balance)} 点</strong><span>${loading?'确认后显示可用次数':'约可用 '+numeric(Math.floor(state.balance/10))+' 次标准分析'}</span></div>${syncLabel()}${button('查看订阅','data-mem-go="membership-plans"')}</aside>`;
  }
  function usage() {
    const omitted=free()&&state.resource==='interactive';
    let content;
    if(state.scenario==='loading')content=`<div class="mem-empty" role="status"><h2>正在读取云端额度</h2><p class="mem-sub">确认前不显示可用数量。</p></div>`;
    else if(state.scenario==='error')content=`<div class="mem-empty" role="alert"><h2>暂时无法同步用量</h2><p class="mem-sub">上次数据待刷新，恢复后重新查询。</p>${button('重试同步','data-mem-retry-usage',true)}</div>`;
    else if(omitted)content=`<div class="mem-empty"><h2>Free 未包含独立分析</h2><p>领地与支招可使用按次包。</p><p class="mem-sub">已拥有报告内的领地和推荐着法可免费查看。</p>${button('查看按次包','data-mem-go="membership-topup"',true)}</div>`;
    else content=usageWindow('h24')+usageWindow('week');
    const note=!accountReady()?'额度和会员信息确认后显示，暂不可创建订单。':free()&&state.resource==='reports'?'本周已用 1 份；24 小时恢复不会另赠周报告。':state.resource==='reports'?'两窗口同时生效，周额度不额外叠加。':'一次分析含领地与支招，切换和重复查看不再扣次。';
    return `<div class="mem-usage"><section class="mem-resource"><div class="mem-resource-tabs" role="tablist" aria-label="资源类型"><button type="button" data-mem-resource="reports" role="tab" aria-selected="${state.resource==='reports'}">复盘报告</button><button type="button" data-mem-resource="interactive" role="tab" aria-selected="${state.resource==='interactive'}">领地与支招</button></div>${content}<p class="mem-footnote">${note}</p></section>${account()}</div>`;
  }
  function plans() {
    return `<section class="mem-plans"><div class="mem-current-plan"><span>${accountReady()?'当前 '+plan().name+' · '+(free()?'每自然周 1 份普通报告':'到期后换档，续费不重置额度'):'账号权益待同步 · 确认后可购买'}</span><span>每份普通报告 ${numeric(500)} visits / 手</span></div><div class="mem-plan-grid">${planCodes.map(code=>{
      const p=catalog[code],current=accountReady()&&code===state.currentPlan;
      return `<article class="mem-plan ${current?'is-current':''}"><div class="mem-plan-head"><strong>${p.name}</strong>${current?'<span>当前套餐</span>':''}</div><div class="mem-plan-price">¥${numeric(p.amount)} <small>/ ${numeric(30)} 天</small></div><p>报告 <strong>${numeric(p.reports[0])}</strong> 份 / ${numeric(24)}h · ${numeric(p.reports[1])} 份 / 周</p><p>互动 <strong>${numeric(p.interactive[0])}</strong> 次 / ${numeric(24)}h · ${numeric(p.interactive[1])} 次 / 周</p><p class="mem-plan-rule">${code==='plus'?'深度报告需使用余额':code==='max'?'容量待验收 · 正式暂不售':`深度报告消耗 ${numeric(4)} 份`}</p>${button(current?'续费 '+p.name:'选择 '+p.name,`data-mem-buy="${code}" ${!online()||!accountReady()||state.futureTerms.length>=16?'disabled':''}`,current)}</article>`;
    }).join('')}</div><div class="mem-plan-footer"><p>深度 ${numeric(2000)} visits 为 ${numeric(4)} 份；每份最多 ${numeric(500)} 手。<br>额度不足时，由你确认是否使用余额。</p>${button('计价说明','data-mem-info="pricing"')}</div></section>`;
  }
  function topup() {
    return `<section class="mem-topup"><article class="mem-pack"><h2>${numeric(100)} 次标准分析包</h2><div class="mem-pack-price">¥${numeric(29)} <small>· ¥${numeric('0.29')} / 标准次</small></div><p>到账 ${numeric(1000)} 点<br>每个标准局面 ${numeric(10)} 点</p><p class="mem-footnote">标准 ${numeric(500)} visits；领地与支招同一份结果。增强 ${numeric(2000)} visits 消耗 ${numeric(4)} 次，约 ¥${numeric('1.16')}。</p>${button('购买按次包',`data-mem-buy="analysis_100_v1" ${!online()||!accountReady()?'disabled':''}`,true)}</article><aside class="mem-pack-detail"><div class="mem-wallet"><span>当前已购余额</span><strong>${accountReady()?numeric(state.balance):'—'} 点</strong><span>${accountReady()?'约 '+numeric(Math.floor(state.balance/10))+' 次标准分析':'等待同步 · 尚未确认'}</span></div><h3>偶尔用，可以按需购买</h3><p>余额为同一池点数，也可支付明确报价的报告等服务。剩余次数是按标准分析估算。</p><p>会员满额参考约 ¥${numeric('0.0498')}–${numeric('0.0967')} / 次；报告权益另含。低频使用按次包总支出可能更低。</p>${button('查看同单位比较','data-mem-info="comparison"')}</aside></section>`;
  }
  const info = {
    pricing:['分析如何计价','标准互动：单个局面 500 visits，10 点（0.29 元）；增强 2000 visits，40 点。一份普通报告含完整主线 0..N 局面，500 visits / 手，最多 500 手。深度报告使用 4 份，Plus 需明确选择余额。报告按余额支付为 max(10, ceil(N/2)) 点；250 手为 125 点，约 3.625 元/盘。整盘批量报告与独立互动的单价不同。'],
    comparison:['按相同标准次比较','用满 30 天互动额度、把整笔会费都分摊到互动的参考价：Plus 0.0967 元/次、Pro 0.066 元/次、Max 0.0498 元/次，报告权益尚未计入。按次包 0.29 元/标准次。上述不是未用满时的实际成本，也不代表会员总是更省；偶尔使用按次包可能总支出更低。'],
  };
  function openOrder(code, trigger) {
    if(!online()||!accountReady())return;
    const startsAt=free()?now():state.futureTerms.at(-1)?.endsAt||state.currentEndsAt;
    const endsAt=startsAt+30*86400000;
    state.order={id:'TEST-'+String(++state.seq).padStart(4,'0'),code,status:'pending',fulfilled:false,startsAt,endsAt,description:orderDates(code,startsAt,endsAt)};
    state.returnFocus=trigger;
    go('membership-checkout');
  }
  function orderDates(code,startsAt,endsAt) {
    if(code==='analysis_100_v1')return '确认后到账 1000 点';
    return free()?'确认后开通至 '+formatDay(endsAt):code===state.currentPlan&&!state.futureTerms.length?'续费至 '+formatDay(endsAt)+'；现有用量保留':formatDay(startsAt)+' '+formatClock(startsAt).slice(0,5)+' 北京时间生效 · 当前排期结束后切换';
  }
  function checkout() {
    const order=state.order;
    if(!order)return '';
    const product=catalog[order.code];
    const labels={pending:'等待 TEST 模拟确认',paid:'模拟支付已确认',failed:'支付未完成，可重新下单',expired:'订单已过期，请重新生成'};
    const status=!accountReady()?'账号信息待同步，暂不确认订单':online()?labels[order.status]:'当前离线，恢复后查询订单';
    return `<div class="mem-dialog-backdrop"><section class="mem-dialog" role="dialog" aria-modal="true" aria-labelledby="mem-checkout-title"><header class="mem-dialog-header"><h2 id="mem-checkout-title">确认购买 · TEST</h2>${button(icon('close'),'data-mem-close-order aria-label="关闭收银台"')}</header><div class="mem-checkout-grid"><div class="mem-qr-placeholder">${icon('test')}<strong>模拟付款区域</strong><span>不可用于真实付款</span></div><div class="mem-order-info"><p>${product.name}${order.code==='analysis_100_v1'?'':' 会员 · 30 天'}</p><p class="mem-order-amount">¥${numeric(product.amount.toFixed(2))}</p><p class="mem-order-meta">账号：fan · 设计示意</p><p class="mem-order-meta">${order.description}</p><div class="mem-order-state ${order.status==='paid'?'is-paid':''}" role="status">${status}</div><p class="mem-order-meta">${order.id} · 测试订单 · ${numeric(15)} 分钟有效</p>${['failed','expired'].includes(order.status)?button('重新生成订单',`data-mem-new-order ${!accountReady()||!online()?'disabled':''}`,true):''}</div></div><p class="mem-dialog-note">以云端订单确认为准。点击“已付款”或返回页面不会增加权益。当前所有金额与状态均为设计示意；正式支付尚未接入。</p><footer class="mem-dialog-actions">${button(order.status==='paid'?'返回用量':'关闭','data-mem-close-order')}</footer></section></div>`;
  }
  function message() {
    if(!state.message)return '';
    const [title,copy]=info[state.message];
    return `<div class="mem-dialog-backdrop"><section class="mem-dialog" role="dialog" aria-modal="true" aria-labelledby="mem-info-title"><header class="mem-dialog-header"><h2 id="mem-info-title">${title}</h2>${button(icon('close'),'data-mem-close-info aria-label="关闭说明"')}</header><p class="mem-info-copy">${copy}</p><footer class="mem-dialog-actions">${button('知道了','data-mem-close-info',true)}</footer></section></div>`;
  }
  function render(screen) {
    if(screen.id==='membership-checkout'&&!state.order&&accountReady()&&online())state.order={id:'TEST-'+String(++state.seq).padStart(4,'0'),code:'analysis_100_v1',status:'pending',fulfilled:false,description:orderDates('analysis_100_v1')};
    const tab=screen.id==='membership-checkout'?(accountReady()?'membership-topup':'membership-usage'):screen.id;
    const content=tab==='membership-plans'?plans():tab==='membership-topup'?topup():usage();
    return `<main class="u-membership" data-fixture-only="true"><header class="mem-head">${button(icon('back')+'返回设置','data-switch="settings"')}<h1>会员与充值</h1><span class="mem-test">TEST · 设计示意</span></header><nav class="mem-tabs" role="tablist" aria-label="会员页面">${[['membership-usage','用量'],['membership-plans','订阅'],['membership-topup','按次充值']].map(([id,label])=>`<button type="button" role="tab" data-mem-go="${id}" aria-selected="${tab===id}">${label}</button>`).join('')}</nav><div class="mem-body">${content}</div>${screen.id==='membership-checkout'?checkout():''}${message()}</main>`;
  }
  ['membership-usage','membership-plans','membership-topup','membership-checkout'].forEach(id=>families[id]=render);
  function updateClock() {
    document.querySelectorAll('[data-mem-countdown]').forEach(element=>{element.textContent=countdown(Number(element.dataset.memCountdown));});
    document.querySelectorAll('[data-mem-sync]').forEach(element=>{element.textContent=formatClock(state.lastSync);});
  }
  function settleDemo(status) {
    const order=state.order;
    if(!order||order.status==='paid'||order.status!=='pending')return;
    if(!online()||!accountReady())return;
    order.status=status;
    if(status==='paid'&&!order.fulfilled){
      order.fulfilled=true;
      if(order.code==='analysis_100_v1')state.balance+=1000;
      else if(free()){state.currentPlan=order.code;state.currentEndsAt=order.endsAt;state.scenario='pro';state.preservedFreeUse=true;}
      else if(order.code===state.currentPlan&&!state.futureTerms.length)state.currentEndsAt=order.endsAt;
      else state.futureTerms.push({code:order.code,startsAt:order.startsAt,endsAt:order.endsAt});
    }
    state.lastSync=now();refresh();
  }
  function makeControls() {
    let controls=document.getElementById('membership-demo-controls');
    if(controls)return controls;
    controls=document.createElement('div');controls.id='membership-demo-controls';controls.className='membership-demo-controls';controls.hidden=true;
    controls.innerHTML=`<label for="membership-preview-scenario">会员设计示意</label><select id="membership-preview-scenario">${scenarios.map(([id,name])=>`<option value="${id}">${name}</option>`).join('')}</select><button type="button" data-mem-demo="paid">模拟成功 / 重放</button><button type="button" data-mem-demo="failed">模拟失败</button><button type="button" data-mem-demo="expired">模拟过期</button><button type="button" data-mem-demo="snapshot">模拟新快照</button><small>固定示意时钟 2026-11-01 12:00 北京时间；仅本页内存，不调用业务 API、不发钱、不创建任务。</small>`;
    document.getElementById('intro').after(controls);return controls;
  }
  window.KioskMembershipInit = id => {
    const controls=makeControls();controls.hidden=!isMembership(id);
    document.getElementById('membership-preview-scenario').value=state.scenario;
    clearInterval(timer);clearInterval(poll);
    if(isMembership(id)){
      timer=setInterval(updateClock,1000);
      poll=setInterval(()=>{if(document.visibilityState==='visible'&&online()&&!['loading','error'].includes(state.scenario)){state.lastSync=now();updateClock();}},15000);
      if(document.querySelector('.mem-dialog'))requestAnimationFrame(()=>document.querySelector('.mem-dialog button')?.focus());
    }
  };
  document.addEventListener('change',event=>{
    if(event.target.id!=='membership-preview-scenario')return;
    state.scenario=event.target.value;state.currentPlan=state.scenario==='free'?'free':'pro';state.currentEndsAt=Date.parse('2026-12-01T04:00:00Z');state.futureTerms=[];state.preservedFreeUse=false;state.message=null;state.boundaryAt=now()+3000;state.boundaryReceived=false;state.lastSync=now();refresh();
  });
  document.addEventListener('click',event=>{
    const target=event.target.closest('[data-mem-go],[data-mem-resource],[data-mem-buy],[data-mem-close-order],[data-mem-new-order],[data-mem-info],[data-mem-close-info],[data-mem-demo],[data-mem-retry-usage]');
    if(!target||target.disabled)return;
    if(target.hasAttribute('data-mem-go'))go(target.dataset.memGo);
    else if(target.hasAttribute('data-mem-resource')){state.resource=target.dataset.memResource;refresh();document.querySelector(`[data-mem-resource="${state.resource}"]`)?.focus();}
    else if(target.hasAttribute('data-mem-buy'))openOrder(target.dataset.memBuy,target.dataset.memBuy);
    else if(target.hasAttribute('data-mem-close-order')){const code=state.returnFocus;go(state.order?.status==='paid'?'membership-usage':state.order?.code==='analysis_100_v1'?'membership-topup':'membership-plans');requestAnimationFrame(()=>document.querySelector(`[data-mem-buy="${code}"]`)?.focus());}
    else if(target.hasAttribute('data-mem-new-order'))openOrder(state.order.code,state.returnFocus);
    else if(target.hasAttribute('data-mem-info')){state.returnFocus=target.dataset.memInfo;state.message=target.dataset.memInfo;refresh();}
    else if(target.hasAttribute('data-mem-close-info')){state.message=null;refresh();document.querySelector(`[data-mem-info="${state.returnFocus}"]`)?.focus();}
    else if(target.hasAttribute('data-mem-retry-usage')){state.scenario='pro';state.lastSync=now();refresh();}
    else if(target.dataset.memDemo==='snapshot'){state.boundaryReceived=true;state.lastSync=now();if(state.scenario==='loading'||state.scenario==='error')state.scenario='pro';refresh();}
    else if(target.hasAttribute('data-mem-demo'))settleDemo(target.dataset.memDemo);
  });
  document.addEventListener('keydown',event=>{
    const dialog=document.querySelector('.mem-dialog');if(!dialog)return;
    if(event.key==='Escape'){event.preventDefault();dialog.querySelector('[data-mem-close-info],[data-mem-close-order]')?.click();}
    if(event.key==='Tab'){
      const buttons=[...dialog.querySelectorAll('button:not(:disabled)')],first=buttons[0],last=buttons.at(-1);
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    }
  });
})();
