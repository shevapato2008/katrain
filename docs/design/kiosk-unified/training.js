/* Training family: six device-reachable states. The home preview board is removed;
   the captured boards on the question list and puzzle screens remain in place. */
(() => {
  const families = window.KioskDesignFamilies = window.KioskDesignFamilies || {};
  const esc = text => String(text).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  const svg = body => `<span class="u-train-icon"><svg viewBox="0 0 24 24" aria-hidden="true">${body}</svg></span>`;
  const icons = {
    life: '<path d="M7 4h10v4h3v9h-5v3H7v-4H4V8h3zM9 8h6m-6 4h6"/>',
    ladder: '<path d="M8 20V5a2 2 0 0 1 4 0v8-6a2 2 0 0 1 4 0v7-3a2 2 0 0 1 4 0v5a5 5 0 0 1-5 5h-4a5 5 0 0 1-3-1Z"/>',
    exchange: '<circle cx="8" cy="12" r="5"/><circle cx="16" cy="12" r="5"/>',
    capture: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18m6-18v18"/>',
    corner: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
    camera: '<path d="M4 7h4l2-2h5l2 2h3v12H4z"/><circle cx="12" cy="13" r="3"/>',
    arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    bulb: '<path d="M9 18h6m-5 3h4M8 16c-1-2-3-3-3-6a7 7 0 0 1 14 0c0 3-2 4-3 6z"/>',
    reset: '<path d="M4 10a8 8 0 0 1 14-4m2-2v5h-5M20 14a8 8 0 0 1-14 4m-2 2v-5h5"/>',
    prev: '<path d="M18 5 9 12l9 7M6 5v14"/>',
    next: '<path d="m6 5 9 7-9 7M18 5v14"/>',
    wrong: '<path d="M5 5 19 19M19 5 5 19"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    physical: '<path d="M3 8h18v10H3zM7 18l-2 3m12-3 2 3M7 11h10M7 15h10M10 8v10m4-10v10"/><circle cx="19" cy="4" r="2"/>',
    mixed: '<circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
    try: '<path d="M4 4h5M4 4v5M20 4h-5m5 0v5M4 20h5m-5 0v-5m16 5h-5m5 0v-5"/><circle cx="12" cy="12" r="3"/>',
  };
  const icon = name => svg(icons[name]);
  const info = detail => `<button class="u-train-info" type="button" aria-label="说明" data-help="${esc(detail)}"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/></svg></button>`;
  const cover = (x, y, width, height) => `<div class="u-train-cover" style="left:${x}px;top:${y}px;width:${width}px;height:${height}px"></div>`;
  const back = (label, id, I) => `<button class="u-train-back" type="button" data-switch="${id}">${I('back')}<span>返回${label}</span></button>`;
  const section = (label, detail = '') => `<div class="u-train-section"><strong>${label}</strong>${detail ? info(detail) : ''}</div>`;
  const stat = (value, label) => `<div class="u-train-stat"><strong>${value}</strong><span>${label}</span></div>`;
  const pageHead = (I, target, id, title, meta = '', action = '') => `<div class="u-train-page-head">${back(target, id, I)}<div class="u-train-page-title"><strong>${title}</strong>${meta ? `<span>${meta}</span>` : ''}</div>${action}</div>`;
  const rankGroups = [
    [{name:'15 级',count:'1000 题'}, {name:'14 级',count:'988 题'}, {name:'13 级',count:'1000 题'}, {name:'12 级',count:'984 题'}, {name:'11 级',count:'986 题'}],
    ['10 级','9 级','8 级','7 级','6 级'].map(name => ({name})),
    ['5 级','4 级','3 级','2 级','1 级'].map(name => ({name})),
    ['1 段','2 段','3 段','4 段','5 段','6 段','7 段'].map(name => ({name})),
  ];
  const selection={rank:'15 级',category:'死活'};
  const capturedSelection=()=>selection.rank==='15 级'&&selection.category==='死活';
  const capturedWrongSelection=()=>selection.rank==='15 级'&&['死活','综合训练'].includes(selection.category);
  const carouselTabs=['15–11 级','10–6 级','5–1 级','1–7 段'];
  const composition=[['吃子',630,'#d9ad67'],['死活',167,'#66c58a'],['手筋',139,'#a19ac4'],['对杀',63,'#6da8ad'],['官子',1,'#d7786c']];
  let carouselGroup=0,carouselIndex=0,carousel=null;
  const mod=(value,length)=>(value%length+length)%length;
  function compositionPie(){let from=0;return `conic-gradient(${composition.map(([,count,color])=>{const start=from;from+=count/10;return `${color} ${start}% ${from}%`;}).join(',')})`;}
  function carouselCard(rank,index){
    const known=rank.name==='15 级';
    const pie=known?`style="--u-train-pie:${compositionPie()}"`:'';
    return `<article class="u-train-carousel-card ${known?'':'is-unknown'}" data-carousel-index="${index}" aria-label="${rank.name}，${known?'题型构成已核实':'题型构成数据暂不可用'}">
      <div class="u-train-carousel-card-head"><strong>${rank.name}</strong><span>${rank.count||'题量暂不可用'}</span></div>
      <div class="u-train-carousel-card-body"><div class="u-train-carousel-pie" ${pie} role="img" aria-label="${known?'吃子 63.0%，死活 16.7%，手筋 13.9%，对杀 6.3%，官子 0.1%':'题型构成数据暂不可用'}"><div>${known?'<strong>1000</strong><span>道题</span>':'<strong>待读取</strong><span>题型比例</span>'}</div></div>
      ${known?`<div class="u-train-carousel-legend">${composition.map(([name,count,color])=>`<div style="--u-train-swatch:${color}"><i></i><span>${name}</span><b>${(count/10).toFixed(1)}%</b><small>${count} 题</small></div>`).join('')}</div>`:'<div class="u-train-carousel-unavailable"><strong>数据暂不可用</strong><span>可继续选择该棋力的题型</span></div>'}</div>
      <button type="button" class="u-train-carousel-enter" data-switch="categories" data-training-rank="${rank.name}" aria-label="进入 ${rank.name} 题型">进入 ${rank.name} 题型 ${icon('arrow')}</button>
    </article>`;
  }
  function training(s, {I}) {
    const group=rankGroups[carouselGroup],index=mod(carouselIndex,group.length);
    return `${cover(0,56,1024,462)}<div class="u-train-home u-train-carousel-home">
      <div class="u-train-carousel-heading"><div><strong>训练营</strong><span>左右滑动卡片，选择棋力</span></div><div class="u-train-carousel-groups" role="tablist" aria-label="棋力范围">${carouselTabs.map((tab,i)=>`<button type="button" role="tab" data-training-group="${i}" aria-selected="${i===carouselGroup}">${tab}</button>`).join('')}</div></div>
      <div class="u-train-carousel-deck" role="region" aria-label="棋力卡片轮播" tabindex="0">${group.map(carouselCard).join('')}</div>
      <button class="u-train-carousel-nav is-prev" type="button" data-carousel-step="-1" aria-label="上一棋力">‹</button><button class="u-train-carousel-nav is-next" type="button" data-carousel-step="1" aria-label="下一棋力">›</button>
      <div class="u-train-carousel-foot"><span data-carousel-position>${String(index+1).padStart(2,'0')} / ${String(group.length).padStart(2,'0')}</span><div data-carousel-track>${group.map((_,i)=>`<i class="${i===index?'is-active':''}"></i>`).join('')}</div><span>手指拖动 · 松手吸附</span></div>
    </div>`;
  }
  const categories = [
    ['死活','10 / 167 题','life'],['手筋','0 / 139 题','ladder'],['对杀','7 / 63 题','exchange'],
    ['吃子','0 / 630 题','capture'],['官子','0 / 1 题','corner'],['综合训练','1000 题 · 20 题/单元','mixed'],
  ];
  function categoriesPage(s,{I}) {
    return `${cover(0,56,1024,544)}<div class="u-train-full">${pageHead(I,'难度','training',`${selection.rank} · 选择题型`,selection.rank==='15 级'?'1000 题 · 5 类':'题量待读取')}
      ${section('选择题型')}
      <div class="u-train-category-grid">${categories.map(([name,count,glyph])=>`<button class="u-train-category" type="button" data-switch="units" data-training-category="${name}">${icon(glyph)}<span><strong>${name}</strong><em>${selection.rank==='15 级'?count:'题量待读取'}</em></span>${icon('arrow')}</button>`).join('')}</div>
    </div>`;
  }
  const unitCards = Array.from({length:9},(_,i)=>({n:i+1,start:i*20+1,end:Math.min((i+1)*20,167),progress:i===0?'50%':'0%'}));
  function unitsPage(s,{I}) {
    return `${cover(0,56,1024,544)}<div class="u-train-full u-train-units">${pageHead(I,'题型','categories',`${selection.rank} · ${selection.category}`)}
      <div class="u-train-stats">${stat('20','每单元题数 · 当前')}${stat(capturedSelection()?'10 / 20':'—','本单元已做对')}${stat('开','做对后自动下一题 · 当前')}</div>
      <div class="u-train-unit-tabs" aria-label="练习分组"><div class="u-train-unit-switch" role="tablist"><button type="button" role="tab" data-unit-tab="units" aria-selected="true">单元</button><button type="button" role="tab" data-unit-tab="wrong" aria-selected="false">错题</button></div>${info('错题簿按当前棋力和题型筛选。这里仅显示 15 级·死活的错题；综合训练则汇集当前等级全部题型的错题。')}</div>
      <div class="u-train-unit-panel" data-unit-panel="units">${capturedSelection()?`<div class="u-train-unit-grid">${unitCards.map(u=>`<button class="u-train-unit-card ${u.n===1?'is-current':''}" type="button" ${u.n===1?'data-switch="problems"':`data-help="第 ${u.n} 单元的题目列表未采集；当前只预览实机已采集的第 1 单元。"`}><span class="u-train-progress-ring"><span>${u.progress}</span></span><span><strong>第 ${u.n} 单元</strong><em>第 ${u.start}–${u.end} 题</em></span></button>`).join('')}</div>`:'<p class="u-train-uncollected">本次未采集这一筛选的单元数据，当前仅展示已核实的入口与状态。</p>'}</div>
      <div class="u-train-unit-panel" data-unit-panel="wrong" hidden><div class="u-train-other-grid"><button type="button" data-switch="tsumego-wrong">${icon('wrong')}<span><strong>错题簿</strong><em>${selection.rank} · ${selection.category} · ${capturedWrongSelection()?'现在有 1 道':'题目记录待读取'}</em></span>${icon('arrow')}</button></div></div>
    </div>`;
  }
  const doneProblems = new Set([1,2,3,4,5,6,7,8,11,13]);
  const recordedTries = {1:1,2:1,3:3,4:3,5:3,6:1,7:1,8:1,9:1,11:1,13:1};
  const problemCard = (n,enter=false) => {const done=doneProblems.has(n),wrong=n===9,tries=recordedTries[n];return `<button class="u-train-problem-cell ${done?'is-done':''} ${wrong?'is-selected':''}" type="button" ${wrong?`data-training-problem="${n}" ${enter?'data-switch="puzzle"':''}`:`data-help="第 ${n} 题的棋形画面未采集；当前只预览第 9 题。"`} aria-label="第 ${n} 题，${done?'已做对':wrong?'做错过，尚未做对':'尚未做过'}"><strong>第 ${n} 题</strong><span>${tries==null?'未做过':`尝试 ${tries} 次`}</span><span>上次 ${wrong?'0:10':'—'}</span></button>`;};
  function boardRail(s,ctx,body) {
    return `${cover(548,56,476,544)}<div class="u-train-board-rail">${body}</div>`;
  }
  function problemsPage(s,{I}) {
    return boardRail(s,null,`${pageHead(I,'单元','units','15 级 · 死活 · 第 1 单元','第 1–20 题 · 落子即判')}
      <div class="u-train-rail-stats">${stat('10 / 20','本单元已做对')}${stat('1.5','平均尝试次数')}${stat('38 秒','平均用时')}</div>
      <div class="u-train-list-tabs" role="tablist" aria-label="题目范围"><button type="button" role="tab" data-problem-tab="all" aria-selected="true">全部题目</button><button type="button" role="tab" data-problem-tab="wrong" aria-selected="false">只做错过的</button></div>
      <div class="u-train-problem-grid" data-problem-panel="all">${Array.from({length:20},(_,i)=>problemCard(i+1)).join('')}</div>
      <div class="u-train-problem-grid" data-problem-panel="wrong" hidden>${problemCard(9)}</div>
      <button class="u-train-enter" type="button" data-switch="puzzle">${I('playbtn')}<span data-selected-problem="true">进入第 09 题</span>${icon('arrow')}</button>`);
  }
  function toggle(label,pressed,disabled=false,detail='') {return `<button class="u-train-switch ${pressed?'is-on':''}" type="button" role="switch" aria-checked="${pressed}" ${disabled?'disabled':''} ${detail?`data-help="${esc(detail)}"`:''}><i></i>${icon(label==='实体盘'?'physical':'try')}<span>${label}</span></button>`;}
  function puzzlePage(s,{I}) {
    const actions = [
      ['bulb','提示','显示或收起提示'],['reset','退一手','退回刚才的一手'],['reset','重摆','从题目初始局面重来'],['prev','上一题','返回上一道题'],['next','下一题','前往下一道题'],
    ];
    return boardRail(s,null,`${pageHead(I,'第 1 单元','problems','第 9 题','15 级 · 死活',`<button class="u-train-calibrate" type="button" data-switch="calib" aria-label="去标定" title="去标定">${icon('camera')}</button>`)}
      <div class="u-train-question"><div class="u-train-card-head"><strong>这一题</strong>${info('黑先。找出那一手；落子即判，走错当场退回。当前为屏幕做题，实体棋盘尚未连接与标定。')}</div><p><b>黑先。</b>找出那一手</p><span>死活 · 15 级</span></div>
      <div class="u-train-moves"><div class="u-train-card-head"><strong>你的走法</strong><span>用时 0:00 · 上次 0:10</span></div><div class="u-train-empty-move">—　还没落子</div></div>
      <div class="u-train-dots"><div class="u-train-card-head"><strong>第 1 单元 · 20 题</strong><span>已做对 ${doneProblems.size} / 20 · 第 9 题</span></div><div class="u-train-dot-grid" role="img" aria-label="第 1 单元进度：第 1 至 8 题和第 11、13 题已做对；当前为第 9 题">${Array.from({length:20},(_,i)=>`<i class="${i===8?'is-now':doneProblems.has(i+1)?'is-done':''}"></i>`).join('')}</div></div>
      <div class="u-train-actions">${toggle('试下',false)}${toggle('实体盘',false,true,'摄像头未连接，实体盘暂不可用。请先连接并标定，再尝试开启。')}${info('试下用于自由探索，不记作正式解题。实体盘需连接摄像头并完成标定。')}${actions.map(([glyph,label,detail])=>`<button type="button" aria-label="${esc(label)}" title="${esc(detail)}">${label==='退一手'?I('undo'):label==='提示'?I('hint'):icon(glyph)}<span>${label}</span></button>`).join('')}</div>`);
  }
  function wrongPage(s,{I}) {
    const hasCapturedWrong=capturedWrongSelection();
    return `${cover(0,56,1024,544)}<div class="u-train-full u-train-wrong">${pageHead(I,'单元','units','错题簿',`${selection.rank} · ${selection.category}`)}
      <div class="u-train-wrong-filter"><span>当前范围：${selection.rank} · ${selection.category}</span><span>${hasCapturedWrong?'未做对的错题 · 共 1 道':'错题数据待读取'}</span></div>
      ${section('题目')}
      <div class="u-train-wrong-grid">${hasCapturedWrong?problemCard(9,true):'<p class="u-train-uncollected">本次未采集这一筛选下的错题记录。</p>'}</div>
      <p class="u-train-wrong-note">本页按当前等级与题型筛选；综合训练汇集当前等级全部题型的错题。</p>
    </div>`;
  }
  Object.assign(families,{
    training,categories:categoriesPage,units:unitsPage,problems:problemsPage,puzzle:puzzlePage,'tsumego-wrong':wrongPage,
  });
  function startCarousel(){
    carousel?.destroy();
    const home=document.querySelector('#stage .u-train-carousel-home');
    if(!home){carousel=null;return;}
    const deck=home.querySelector('.u-train-carousel-deck'),cards=[...deck.querySelectorAll('.u-train-carousel-card')];
    const positionLabel=home.querySelector('[data-carousel-position]'),track=[...home.querySelectorAll('[data-carousel-track] i')];
    const length=cards.length;
    let position=mod(carouselIndex,length),drag=null,paintFrame=0,snapFrame=0,shownIndex=-1,ignoreClickUntil=0;
    const nearestDelta=(index,at)=>{let delta=index-at;while(delta>length/2)delta-=length;while(delta<-length/2)delta+=length;return delta;};
    const scale=()=>home.getBoundingClientRect().width/992||1;
    function syncActive(index){
      if(index===shownIndex)return;
      shownIndex=index;carouselIndex=index;
      cards.forEach((card,i)=>{
        const delta=nearestDelta(i,index),center=delta===0;
        card.classList.toggle('is-center',center);
        card.classList.toggle('is-side-left',delta<0);
        card.classList.toggle('is-side-right',delta>0);
        card.style.zIndex=String(90-Math.round(Math.abs(delta)*20));
        card.style.pointerEvents=Math.abs(delta)>1?'none':'auto';
        card.setAttribute('aria-current',String(center));
      });
      positionLabel.innerHTML=`<span class="kiosk-plex-num">${String(index+1).padStart(2,'0')}</span> / <span class="kiosk-plex-num">${String(length).padStart(2,'0')}</span>`;
      track.forEach((dot,i)=>dot.classList.toggle('is-active',i===index));
    }
    function layout(){
      syncActive(mod(Math.round(position),length));
      cards.forEach((card,i)=>{
        const delta=nearestDelta(i,position),distance=Math.abs(delta);
        const x=delta*421/(1+distance*.04),size=Math.max(.40,1-distance*.51),depth=-distance*108,yaw=Math.max(-32,Math.min(32,-delta*17));
        card.style.transform=`translate3d(calc(-50% + ${x}px),-50%,${depth}px) rotateY(${yaw}deg) scale(${size})`;
        card.style.opacity=distance>1.55?'0':String(Math.max(.89,1-distance*.05));
      });
    }
    function settle(target){
      cancelAnimationFrame(snapFrame);cancelAnimationFrame(paintFrame);
      const start=position,distance=target-start,reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
      const duration=reduced?0:Math.min(390,260+Math.abs(distance)*65),began=performance.now();
      const tick=now=>{
        const time=duration?Math.min(1,(now-began)/duration):1,eased=1-Math.pow(1-time,3);
        position=start+distance*eased;layout();
        if(time<1)snapFrame=requestAnimationFrame(tick);
        else {snapFrame=0;position=mod(target,length);layout();}
      };
      snapFrame=requestAnimationFrame(tick);
    }
    function step(amount){if(!drag)settle(Math.round(position)+amount);}
    function down(event){
      if(event.pointerType==='mouse'&&event.button!==0)return;
      cancelAnimationFrame(snapFrame);snapFrame=0;
      const x=event.clientX/scale();
      drag={id:event.pointerId,startX:x,lastX:x,startPos:position,lastTime:performance.now(),velocity:0,moved:false};
    }
    function move(event){
      if(!drag||drag.id!==event.pointerId)return;
      const x=event.clientX/scale(),delta=x-drag.startX;
      if(!drag.moved){
        if(Math.abs(delta)<7)return;
        drag.moved=true;deck.setPointerCapture(event.pointerId);deck.classList.add('is-dragging');
      }
      const now=performance.now(),elapsed=Math.max(1,now-drag.lastTime);
      drag.velocity=.55*drag.velocity+.45*(x-drag.lastX)/elapsed;
      drag.lastX=x;drag.lastTime=now;
      position=drag.startPos-delta/285;
      cancelAnimationFrame(paintFrame);paintFrame=requestAnimationFrame(layout);
    }
    function finish(event){
      if(!drag||drag.id!==event.pointerId)return;
      const ended=drag;drag=null;deck.classList.remove('is-dragging');
      if(!ended.moved){settle(Math.round(position));return;}
      ignoreClickUntil=performance.now()+420;
      cancelAnimationFrame(paintFrame);
      position=ended.startPos-(ended.lastX-ended.startX)/285;layout();
      let target=Math.round(position-ended.velocity*.2);
      if(target===Math.round(ended.startPos)&&(Math.abs(ended.lastX-ended.startX)>48||Math.abs(ended.velocity)>.6))target=Math.round(ended.startPos)+Math.sign(ended.startX-ended.lastX);
      settle(target);
    }
    function key(event){
      if(!home.isConnected||!home.contains(document.activeElement))return;
      if(event.key==='ArrowLeft'||event.key==='ArrowRight'){
        event.preventDefault();step(event.key==='ArrowLeft'?-1:1);
      }
    }
    deck.addEventListener('pointerdown',down);deck.addEventListener('pointermove',move);
    deck.addEventListener('pointerup',finish);deck.addEventListener('pointercancel',finish);
    window.addEventListener('keydown',key);
    layout();
    carousel={
      step,settle,
      choose(index){settle(Math.round(position+nearestDelta(index,position)));},
      suppressClick(){return performance.now()<ignoreClickUntil;},
      isCentered(index){return mod(Math.round(position),length)===index;},
      destroy(){cancelAnimationFrame(snapFrame);cancelAnimationFrame(paintFrame);window.removeEventListener('keydown',key);deck.removeEventListener('pointerdown',down);deck.removeEventListener('pointermove',move);deck.removeEventListener('pointerup',finish);deck.removeEventListener('pointercancel',finish);},
    };
  }
  window.KioskTrainingInit=startCarousel;
  document.addEventListener('click',event=>{
    const carouselHome=event.target.closest('.u-train-carousel-home');
    if(carouselHome){
      if(carousel?.suppressClick()){event.preventDefault();event.stopPropagation();return;}
      const groupButton=event.target.closest('[data-training-group]');
      if(groupButton){carouselGroup=Number(groupButton.dataset.trainingGroup);carouselIndex=0;window.KioskTrainingRefresh?.();return;}
      const stepButton=event.target.closest('[data-carousel-step]');
      if(stepButton){carousel?.step(Number(stepButton.dataset.carouselStep));return;}
      const card=event.target.closest('[data-carousel-index]');
      if(card){const index=Number(card.dataset.carouselIndex);if(!carousel?.isCentered(index)){carousel?.choose(index);event.preventDefault();event.stopPropagation();return;}}
    }
    const rankChoice=event.target.closest('[data-training-rank]');if(rankChoice)selection.rank=rankChoice.dataset.trainingRank;
    const categoryChoice=event.target.closest('[data-training-category]');if(categoryChoice)selection.category=categoryChoice.dataset.trainingCategory;
    const unitTab=event.target.closest('[data-unit-tab]');
    if(unitTab){
      const page=unitTab.closest('.u-train-units');
      page.querySelectorAll('[data-unit-tab]').forEach(button=>button.setAttribute('aria-selected',String(button===unitTab)));
      page.querySelectorAll('[data-unit-panel]').forEach(panel=>panel.hidden=panel.dataset.unitPanel!==unitTab.dataset.unitTab);
    }
    const problemTab=event.target.closest('[data-problem-tab]');
    if(problemTab){const rail=problemTab.closest('.u-train-board-rail');rail.querySelectorAll('[data-problem-tab]').forEach(button=>button.setAttribute('aria-selected',String(button===problemTab)));rail.querySelectorAll('[data-problem-panel]').forEach(panel=>panel.hidden=panel.dataset.problemPanel!==problemTab.dataset.problemTab);}
    const problem=event.target.closest('[data-training-problem]');
    if(problem){const area=problem.closest('.u-train-board-rail,.u-train-wrong');area.querySelectorAll('[data-training-problem]').forEach(button=>button.classList.toggle('is-selected',button===problem));const label=area.querySelector('[data-selected-problem]');if(label)label.textContent=`进入第 ${problem.dataset.trainingProblem} 题`;}
    const switchButton=event.target.closest('.u-train-switch:not(:disabled)');
    if(switchButton){
      const on=switchButton.getAttribute('aria-checked')!=='true';
      switchButton.setAttribute('aria-checked',String(on));switchButton.classList.toggle('is-on',on);
    }
  },true);
})();
