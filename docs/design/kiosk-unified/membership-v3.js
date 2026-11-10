/* v3 isolated design fixture: in-memory only, without API, payment or device calls. */
(() => {
  'use strict';
  const families = window.KioskDesignFamilies = window.KioskDesignFamilies || {};
  const params = new URLSearchParams(location.search);
  const epoch = Date.parse('2026-11-01T04:00:00Z');
  const started = performance.now();
  const now = () => epoch + performance.now() - started;
  const termEnd = Date.parse('2026-12-01T04:00:00Z');
  const weekEnd = Date.parse('2026-11-01T16:00:00Z');
  const catalog = {
    free:{name:'Free'},
    plus:{name:'Plus',amount:29,term:9030,week:2107,reports:30,weeklyReports:7,saving:68},
    pro:{name:'Pro',amount:99,term:36120,week:8428,reports:120,weeklyReports:28,saving:73},
    max:{name:'Max',amount:299,term:117390,week:27391,reports:390,weeklyReports:91,saving:75},
  };
  const planCodes = ['plus','pro','max'];
  const scenarios = [['pro','Pro 会员'],['free','Free 周报告'],['exhausted','周额度耗尽'],['not-started','新周期未使用'],['reserved','分析已预留'],['offline','离线旧数据'],['boundary','周界待重取'],['loading','加载中'],['error','同步失败']];
  const initial = scenarios.some(([id]) => id === params.get('membership-state')) ? params.get('membership-state') : 'pro';
  const state = {scenario:initial,currentPlan:initial==='free'?'free':'pro',balance:1000,amount:30,order:null,seq:0,message:null,lastSync:epoch,boundaryAt:now()+3000,boundaryReceived:false,returnFocus:null,currentEndsAt:termEnd,futureTerms:[],freeUsed:1,priorWeeklyUse:0};
  let timer, poll;
  const numeric = value => `<span class="kiosk-plex-num">${value}</span>`;
  const whole = value => numeric(Number(value).toLocaleString('en-US'));
  const points = credits => numeric((credits/100).toFixed(2));
  const paths = {
    back:'<path d="m15 4-8 8 8 8M7 12h15"/>',
    close:'<path d="m6 6 12 12M18 6 6 18"/>',
    info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
  };
  const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name]}</svg>`;
  const button = (label,attrs='',primary=false) => `<button type="button" ${primary?'class="mem-primary"':''} ${attrs}>${label}</button>`;
  const infoButton = key => button(icon('info'),`class="mem-info" data-mem-info="${key}" aria-label="${key==='pricing'?'API计价说明':'会员额度与优惠说明'}"`);
  const refresh = () => window.KioskMembershipRefresh?.();
  const go = id => location.hash==='#'+id ? refresh() : location.hash=id;
  const isMembership = id => id?.startsWith('membership-');
  const free = () => state.currentPlan==='free';
  const plan = () => catalog[state.currentPlan];
  const online = () => state.scenario!=='offline';
  const boundaryPending = () => state.scenario==='boundary' && now()>=state.boundaryAt && !state.boundaryReceived;
  const accountReady = () => !['loading','error'].includes(state.scenario) && !boundaryPending();
  const purchasable = () => online() && accountReady();
  const format = (value,options) => new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',hour12:false,...options}).format(new Date(value));
  const formatClock = value => format(value,{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  const formatDay = value => format(value,{year:'numeric',month:'2-digit',day:'2-digit'});
  const formatDate = value => format(value,{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
  function countdown(at) {
    const seconds=Math.max(0,Math.ceil((at-now())/1000));
    if(!seconds)return '等待云端核对';
    const days=Math.floor(seconds/86400),hours=Math.floor(seconds%86400/3600),minutes=Math.floor(seconds%3600/60),remain=seconds%60;
    return `${days?days+'天 ':''}${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}:${String(remain).padStart(2,'0')}`;
  }
  function usageData(period) {
    const limit=plan()[period];
    let used=period==='term'?9030:1505,reserved=301;
    if(state.scenario==='not-started'){used=period==='week'?state.priorWeeklyUse:0;reserved=0;}
    if(state.scenario==='reserved')reserved=602;
    if(state.scenario==='exhausted'&&period==='week'){used=limit;reserved=0;}
    const remaining=Math.max(0,limit-used-reserved);
    return {limit,used,reserved,remaining,percent:Math.round(remaining/limit*1000)/10};
  }
  function syncLabel() {
    if(!accountReady())return '<div class="mem-sync is-stale">额度尚未确认</div>';
    return `<div class="mem-sync ${!online()?'is-stale':''}"><i></i><span>${online()?'已同步':'旧数据'} · <time data-mem-sync>${formatClock(state.lastSync)}</time></span></div>`;
  }
  function accountStatus() {
    if(state.scenario==='loading')return '账号待同步 · 暂不可购买';
    if(state.scenario==='error')return '同步失败 · 暂不可购买';
    if(!online())return '离线旧数据 · 暂不可购买';
    if(boundaryPending())return '周界待确认 · 暂不可购买';
    return '';
  }
  function usageWindow(period) {
    const data=usageData(period);
    const reset=period==='term'?state.currentEndsAt:state.scenario==='boundary'&&!state.boundaryReceived?state.boundaryAt:weekEnd;
    return `<article class="mem-limit"><div class="mem-limit-heading"><strong>${period==='term'?'本期 · 30天':'本周'}</strong><span>${whole(data.remaining)} / ${whole(data.limit)} 标准单位</span></div><div class="mem-progress" role="progressbar" aria-label="${period==='term'?'本期':'本周'}剩余比例" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${data.percent}"><i style="width:${data.percent}%"></i></div><div class="mem-limit-detail"><span>已用 ${whole(data.used)} · 预留 ${whole(data.reserved)}</span><span>${numeric(data.percent)}% 剩余</span></div><div class="mem-limit-reset">${period==='term'?'到期':'周一零点重置'} <time>${numeric(formatDate(reset))}</time><span>北京时间</span></div></article>`;
  }
  function account() {
    const ready=accountReady();
    const future=state.futureTerms[0];
    return `<aside class="mem-aside"><div class="mem-account"><strong>${ready?plan().name:'待同步'}</strong><span class="mem-badge">${ready?'当前权益':'尚未确认'}</span></div><p>${!ready?'账号权益确认后显示':free()?'每周1份普通报告资格':`有效至 ${numeric(formatDay(state.currentEndsAt))}`}</p><div class="mem-wallet"><span>API余额</span><strong>${ready?points(state.balance):'—'} 积分</strong><span>充值与会员是两种选择</span></div>${syncLabel()}${future?`<p>下期 ${catalog[future.code].name}<br>${numeric(formatDay(future.startsAt))} 生效</p>`:'<p>不会自动改用余额扣费</p>'}<div class="mem-account-actions">${button('API充值','data-mem-go="membership-topup"')}${button('查看会员','data-mem-go="membership-plans"')}</div></aside>`;
  }
  function usage() {
    let content;
    if(!accountReady())content=`<div class="mem-empty" role="status"><h2>${state.scenario==='error'?'暂时无法同步用量':'额度正在确认'}</h2><p>确认前不显示可用数量，也不创建订单。</p>${button('重取示意快照','data-mem-retry-usage',true)}</div>`;
    else if(free())content=`<section class="mem-free"><div class="mem-section-heading"><h2>每周免费普通报告</h2>${infoButton('quota')}</div><p class="mem-free-count">剩余 ${numeric(Math.max(0,1-state.freeUsed))} / ${numeric(1)} 份</p><p>本周已用 ${numeric(state.freeUsed)} 份 · 不赠通用分析额度</p><div class="mem-progress" role="progressbar" aria-label="免费报告剩余比例" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${state.freeUsed?0:100}"><i style="width:${state.freeUsed?0:100}%"></i></div><p>周一零点重置 · 北京时间</p><p class="mem-footnote">已拥有结果可反复查看；领地与支招含在同一结果内。</p></section>`;
    else {
      const available=Math.min(usageData('term').remaining,usageData('week').remaining);
      content=`<div class="mem-available"><div><span>当前可用 · 取两者较小值</span><strong>${whole(available)} <small>标准单位</small></strong></div>${infoButton('quota')}</div>${usageWindow('term')}${usageWindow('week')}<p class="mem-footnote">一次结果含领地与支招；重复查看与切换不重复扣费。</p>`;
    }
    return `<div class="mem-usage"><section class="mem-resource">${content}</section>${account()}</div>`;
  }
  function plans() {
    return `<section class="mem-plans"><div class="mem-comparison-heading"><span>会员 · ${numeric(30)}天 · 候选价格</span><span>对比API普通 ${numeric('0.01')}积分 / 局面</span>${infoButton('quota')}</div><div class="mem-plan-grid">${planCodes.map(code=>{
      const p=catalog[code],current=accountReady()&&code===state.currentPlan;
      return `<article class="mem-plan ${current?'is-current':''} ${code==='max'?'is-unavailable':''}"><div class="mem-plan-head"><strong>${p.name}</strong><span>${code==='max'?'暂未开放':current?'当前会员':''}</span></div><div class="mem-plan-price">¥${numeric(p.amount)} <small>/ ${numeric(30)}天</small></div><p class="mem-saving">比API约省 ${numeric(p.saving)}%</p><div class="mem-report-reference"><strong>约 ${numeric(p.reports)} 盘 / ${numeric(30)}天</strong><span>每周最多约 ${numeric(p.weeklyReports)} 盘</span></div><div class="mem-plan-units"><span>${whole(p.term)} 标准单位 / ${numeric(30)}天</span><span>${whole(p.week)} 标准单位 / 周</span></div>${button(code==='max'?'暂未开放':current?'续费 '+p.name:'选择 '+p.name,`data-mem-buy="${code}" ${code==='max'||!purchasable()?'disabled':''}`,code==='pro')}</article>`;
    }).join('')}</div><div class="mem-plan-footer"><p>按${numeric(30)}天额度用满计算；实际优惠随用量变化<br>按${numeric(300)}手估算，受本周与本期剩余共同限制</p></div></section>`;
  }
  function topup() {
    return `<section class="mem-topup"><article class="mem-api-rates"><div class="mem-section-heading"><h2>API充值 · 按用量付费</h2>${infoButton('pricing')}</div><div class="mem-rate"><span>普通分析</span><strong>约 ${numeric('0.01')} 积分 / 手</strong></div><div class="mem-rate"><span>高级分析</span><strong>约 ${numeric('0.04')} 积分 / 手</strong></div><p class="mem-report-quote">${numeric(300)}手报告 · 普通 ${numeric('3.01')} 积分<br>高级 ${numeric('12.04')} 积分，均含初始局面</p><p class="mem-footnote">一次结果含领地与支招，不重复收费。<br>实际棋谱报价确认后，再开始分析。</p><div class="mem-alternative"><span>经常使用，会员可更省</span>${button('比较会员','data-mem-go="membership-plans"')}</div></article><aside class="mem-recharge"><div class="mem-recharge-balance"><span>当前API余额</span><strong>${accountReady()?points(state.balance):'—'} 积分</strong></div><p class="mem-exchange">${numeric(1)}元 = ${numeric(1)}积分</p><div class="mem-amounts" role="group" aria-label="选择API充值金额">${[10,30,100].map(amount=>`<button type="button" data-mem-amount="${amount}" aria-pressed="${state.amount===amount}"><strong>¥${numeric(amount)}</strong><span>${numeric(amount)}积分</span></button>`).join('')}</div><p class="mem-selected">到账 ${numeric(state.amount.toFixed(2))} 积分</p>${button('预览充值 ¥'+numeric(state.amount),`data-mem-buy="wallet" ${!purchasable()?'disabled':''}`,true)}<p class="mem-footnote">TEST设计示意 · 不会真实收款</p></aside></section>`;
  }
  const info = {
    pricing:['API计价说明',[
      '1元 = 1积分；余额以0.01积分精度显示。',
      '普通500 visits：每局面0.01积分。高级2000 visits：每局面0.04积分。',
      'N手报告计入初始局面，共N+1个局面。300手普通3.01积分，高级12.04积分；实际按棋谱报价。',
      '单次结果同时含领地与支招；切换、重复查看已拥有的结果不扣费。不会自动从会员切到余额。',
    ]],
    quota:['会员额度与优惠说明',[
      '1标准单位 = 1个普通500 visits局面；高级2000 visits消耗4单位。同一结果包含领地与支招。',
      '报告按N+1局面使用额度；300手普通报告为301单位。盘数仅作估算，由实际棋谱与两项剩余额度共同决定。',
      '本期30天，到期不恢复；每周按Asia/Shanghai周一00:00重置。可用额度取本期与本周剩余的较小值。',
      '优惠与API普通0.01积分/局面相比，按30天额度用满计算；未用满时实际优惠随用量变化。价格及额度均为候选预览，Max暂未开放。',
      'Free每周仅1份普通报告资格，不赠通用标准单位。',
    ]],
  };
  function openOrder(code,trigger) {
    if(!purchasable()||code==='max'||(!catalog[code]&&code!=='wallet'))return;
    const startsAt=free()?now():state.futureTerms.at(-1)?.endsAt||state.currentEndsAt;
    state.order={id:'TEST-'+String(++state.seq).padStart(4,'0'),code,amount:code==='wallet'?state.amount:catalog[code].amount,status:'pending',fulfilled:false,startsImmediately:free(),startsAt,endsAt:startsAt+30*86400000};
    state.returnFocus=trigger;
    go('membership-checkout');
  }
  function checkout() {
    const order=state.order;
    if(!order)return `<div class="mem-dialog-backdrop"><section class="mem-dialog" role="dialog" aria-modal="true" aria-labelledby="mem-checkout-title"><header class="mem-dialog-header"><h2 id="mem-checkout-title">购买预览 · TEST</h2>${button(icon('close'),'class="mem-close" data-mem-close-order aria-label="关闭预览"')}</header><p>先选择API充值金额或会员套餐。</p><p class="mem-dialog-note">账号和额度确认后才能创建测试预览。</p><footer class="mem-dialog-actions">${button('返回选择','data-mem-close-order',true)}</footer></section></div>`;
    const wallet=order.code==='wallet';
    const statuses={pending:'等待TEST模拟确认',paid:'TEST预览已确认',failed:'TEST未完成，可重新预览',expired:'TEST预览已过期'};
    const detail=wallet?`到账 ${numeric(order.amount.toFixed(2))} 积分`:`${catalog[order.code].name}会员 · ${numeric(30)}天`;
    return `<div class="mem-dialog-backdrop"><section class="mem-dialog" role="dialog" aria-modal="true" aria-labelledby="mem-checkout-title"><header class="mem-dialog-header"><h2 id="mem-checkout-title">${wallet?'充值':'会员'}确认 · TEST</h2>${button(icon('close'),'class="mem-close" data-mem-close-order aria-label="关闭预览"')}</header><div class="mem-order-summary"><div><p>${detail}</p><p class="mem-order-meta">${wallet?'API余额按用量扣费':order.startsImmediately?'确认后模拟开通，本周已用保留':'当前会员到期后生效，现有用量保留'}</p></div><strong>¥${numeric(order.amount.toFixed(2))}</strong></div>${!wallet?`<p class="mem-order-meta">${numeric(formatDay(order.startsAt))} 至 ${numeric(formatDay(order.endsAt))} · 北京时间</p>`:''}<p class="mem-order-state" role="status">${!accountReady()?'账号信息待同步，暂不可确认':!online()?'当前离线，恢复同步后再确认':statuses[order.status]}</p><p class="mem-order-meta">${order.id} · 仅内存示意</p><p class="mem-dialog-note">仅用于检查购买流程，不会真实付款、充值或改变账号权益。</p><footer class="mem-dialog-actions">${button(order.status==='paid'?'返回用量':'返回选择','data-mem-close-order')}${order.status==='pending'?button('TEST确认预览',`data-mem-confirm ${!purchasable()?'disabled':''}`,true):['failed','expired'].includes(order.status)?button('重新预览',`data-mem-new-order ${!purchasable()?'disabled':''}`,true):''}</footer></section></div>`;
  }
  function message() {
    if(!state.message)return '';
    const [title,paragraphs]=info[state.message];
    return `<div class="mem-dialog-backdrop"><section class="mem-dialog" role="dialog" aria-modal="true" aria-labelledby="mem-info-title"><header class="mem-dialog-header"><h2 id="mem-info-title">${title}</h2>${button(icon('close'),'class="mem-close" data-mem-close-info aria-label="关闭说明"')}</header><div class="mem-info-copy">${paragraphs.map(copy=>`<p>${copy}</p>`).join('')}</div><footer class="mem-dialog-actions">${button('知道了','data-mem-close-info',true)}</footer></section></div>`;
  }
  function render(screen) {
    const tab=screen.id==='membership-checkout'?(state.order?.code==='wallet'||!state.order?'membership-topup':'membership-plans'):screen.id;
    const status=accountStatus();
    const content=tab==='membership-plans'?plans():tab==='membership-topup'?topup():usage();
    return `<main class="u-membership" data-fixture-only="true"><header class="mem-head">${button(icon('back')+'返回设置','data-switch="settings"')}<h1>会员与充值</h1><span class="mem-test ${status?'mem-account-status':''}" role="status">${status||'TEST · 设计示意'}</span></header><nav class="mem-tabs" role="tablist" aria-label="会员与充值">${[['membership-usage','用量'],['membership-topup','API充值'],['membership-plans','会员']].map(([id,label])=>`<button type="button" role="tab" data-mem-go="${id}" aria-selected="${tab===id}">${label}</button>`).join('')}</nav><div class="mem-body">${content}</div>${screen.id==='membership-checkout'?checkout():''}${message()}</main>`;
  }
  ['membership-usage','membership-plans','membership-topup','membership-checkout'].forEach(id=>families[id]=render);
  function updateClock() {
    document.querySelectorAll('[data-mem-countdown]').forEach(element=>{element.textContent=countdown(Number(element.dataset.memCountdown));});
    document.querySelectorAll('[data-mem-sync]').forEach(element=>{element.textContent=formatClock(state.lastSync);});
    if(boundaryPending()&&!document.querySelector('.mem-account-status'))refresh();
  }
  function settleDemo(status) {
    const order=state.order;
    if(!order||order.status!=='pending'||!purchasable())return;
    order.status=status;
    if(status==='paid'&&!order.fulfilled){
      order.fulfilled=true;
      if(order.code==='wallet')state.balance+=order.amount*100;
      else if(free()){state.priorWeeklyUse=state.freeUsed*301;state.currentPlan=order.code;state.currentEndsAt=order.endsAt;state.scenario='not-started';}
      else state.futureTerms.push({code:order.code,startsAt:order.startsAt,endsAt:order.endsAt});
    }
    state.lastSync=now();refresh();
  }
  function makeControls() {
    let controls=document.getElementById('membership-demo-controls');
    if(controls)return controls;
    controls=document.createElement('div');controls.id='membership-demo-controls';controls.className='membership-demo-controls';controls.hidden=true;
    controls.innerHTML=`<label for="membership-preview-scenario">会员设计示意</label><select id="membership-preview-scenario">${scenarios.map(([id,name])=>`<option value="${id}">${name}</option>`).join('')}</select><button type="button" data-mem-demo="paid">模拟确认 / 重放</button><button type="button" data-mem-demo="failed">模拟未完成</button><button type="button" data-mem-demo="expired">模拟过期</button><button type="button" data-mem-demo="snapshot">模拟新快照</button><small>固定示意时钟2026-11-01 12:00北京时间；仅本页内存，不调用API、真实付款或创建分析任务。</small>`;
    document.getElementById('intro')?.after(controls);return controls;
  }
  window.KioskMembershipInit = id => {
    const controls=makeControls();controls.hidden=!isMembership(id);
    controls.querySelector('select').value=state.scenario;
    clearInterval(timer);clearInterval(poll);
    if(isMembership(id)){
      timer=setInterval(updateClock,1000);
      poll=setInterval(()=>{if(document.visibilityState==='visible'&&online()&&accountReady()){state.lastSync=now();updateClock();}},15000);
      if(document.querySelector('.mem-dialog'))requestAnimationFrame(()=>document.querySelector('.mem-dialog button')?.focus());
    }
  };
  function takeSnapshot() {
    state.boundaryReceived=true;state.lastSync=now();
    if(['loading','error'].includes(state.scenario))state.scenario='pro';
    refresh();
  }
  document.addEventListener('change',event=>{
    if(event.target.id!=='membership-preview-scenario')return;
    state.scenario=event.target.value;state.currentPlan=state.scenario==='free'?'free':'pro';state.currentEndsAt=termEnd;state.futureTerms=[];state.freeUsed=1;state.priorWeeklyUse=0;state.message=null;state.boundaryAt=now()+3000;state.boundaryReceived=false;state.lastSync=now();refresh();
  });
  document.addEventListener('click',event=>{
    const target=event.target.closest('[data-mem-go],[data-mem-amount],[data-mem-buy],[data-mem-close-order],[data-mem-new-order],[data-mem-confirm],[data-mem-info],[data-mem-close-info],[data-mem-demo],[data-mem-retry-usage]');
    if(!target||target.disabled)return;
    if(target.hasAttribute('data-mem-go'))go(target.dataset.memGo);
    else if(target.hasAttribute('data-mem-amount')){state.amount=Number(target.dataset.memAmount);refresh();document.querySelector(`[data-mem-amount="${state.amount}"]`)?.focus();}
    else if(target.hasAttribute('data-mem-buy'))openOrder(target.dataset.memBuy,target.dataset.memBuy);
    else if(target.hasAttribute('data-mem-close-order')){const code=state.returnFocus;go(state.order?.status==='paid'?'membership-usage':state.order?.code==='wallet'||!state.order?'membership-topup':'membership-plans');requestAnimationFrame(()=>document.querySelector(`[data-mem-buy="${code}"]`)?.focus());}
    else if(target.hasAttribute('data-mem-new-order'))openOrder(state.order.code,state.returnFocus);
    else if(target.hasAttribute('data-mem-confirm'))settleDemo('paid');
    else if(target.hasAttribute('data-mem-info')){state.returnFocus=target.dataset.memInfo;state.message=target.dataset.memInfo;refresh();}
    else if(target.hasAttribute('data-mem-close-info')){state.message=null;refresh();document.querySelector(`[data-mem-info="${state.returnFocus}"]`)?.focus();}
    else if(target.hasAttribute('data-mem-retry-usage')||target.dataset.memDemo==='snapshot')takeSnapshot();
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
