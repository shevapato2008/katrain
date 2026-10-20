/* Settings and calibration. This file only paints the HTML design comparison.
   Board connection examples are explicitly marked as design preview states. */
(() => {
  const F = window.KioskDesignFamilies = window.KioskDesignFamilies || {};
  const esc = value => String(value).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  const paths = {
    camera:'<path d="M4 7h4l2-2h5l2 2h3v12H4z"/><circle cx="12" cy="13" r="3"/>',
    physical:'<path d="M3 8h18v10H3zM7 18l-2 3m12-3 2 3M7 11h10M7 15h10M10 8v10m4-10v10"/><circle cx="19" cy="4" r="2"/>',
    hand:'<path d="M8 13V5a2 2 0 0 1 4 0v6-3a2 2 0 0 1 4 0v4-2a2 2 0 0 1 4 0v7a5 5 0 0 1-5 5h-5a5 5 0 0 1-4-2l-4-5a2 2 0 0 1 3-3z"/>',
    sound:'<path d="M4 9v6h4l5 4V5L8 9zM17 9a5 5 0 0 1 0 6m2-9a9 9 0 0 1 0 12"/>',
    globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c-4 4-4 14 0 18m0-18c4 4 4 14 0 18"/>',
    typography:'<path d="M3 5h12M9 5v15M5 20h8M16 11h5M18.5 11v9M16 20h5"/>',
    info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
    arrow:'<path d="m15 4-8 8 8 8M7 12h15"/>',
    check:'<path d="m4 12 5 5L20 6"/>',
    chevron:'<path d="m6 9 6 6 6-6"/>',
    next:'<path d="m9 5 7 7-7 7"/>',
    settings:'<path d="M10 2h4l.6 2.1 1.5.6 1.9-1.1 2.8 2.8-1.1 1.9.6 1.5L22 10v4l-2.1.6-.6 1.5 1.1 1.9-2.8 2.8-1.9-1.1-1.5.6L14 22h-4l-.6-2.1-1.5-.6-1.9 1.1-2.8-2.8 1.1-1.9-.6-1.5L2 14v-4l2.1-.6.6-1.5-1.1-1.9L6.4 3l1.9 1.1 1.5-.6z"/><circle cx="12" cy="12" r="3"/>',
  };
  const icon = name => `<svg class="u-settings-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths[name]}</svg>`;
  const help = copy => `<button class="u-settings-help" type="button" aria-label="说明" data-help="${esc(copy)}">${icon('info')}</button>`;
  const sections = [
    ['board','实体盘','physical','settings-board'],
    ['move','落子与提示','hand','settings-move'],
    ['sound','声音','sound','settings-sound'],
    ['language','语言','globe','settings-language'],
    ['typography','字体与字号','typography','settings-typography'],
    ['about','关于','info','settings-about'],
  ];
  const heading = (name, note='') => `<div class="u-settings-section-head"><strong>${name}</strong>${note ? help(note) : ''}<span></span></div>`;
  const row = (title, end='', sub='', extra='') => `<div class="u-settings-row ${extra}"><div class="u-settings-row-text"><strong>${title}</strong>${sub ? `<small>${sub}</small>` : ''}</div>${end}</div>`;
  const tag = (value, good=false) => `<span class="u-settings-tag ${good?'is-good':''}">${value}</span>`;
  const button = (label, switchTo='', detail='') => `<button class="u-settings-row-button" type="button" ${switchTo ? `data-switch="${switchTo}"` : `data-help="${esc(detail)}"`}>${label}</button>`;
  const preferences = {autoAdvance:true,sfx:true,voice:true,language:'cn'};
  const typographyState=window.KioskDesignTypography.state;
  const fontChoices = [['wenkai','霞鹜楷体','当前 · 默认'],['kaiti','楷体','常规楷书'],['lishu','隶书','隶变体'],['heiti','黑体','清晰有力']];
  const sizeChoices = [['large','当前（最大）'],['medium','小一档'],['small','小两档']];
  const typography = () => `<section class="u-settings-section u-settings-typography" data-group="typography">${heading('字体与字号','选择立即应用于所有围棋设计页面，浏览器重新打开后保留。字号从当前最大值依次缩小两档。四个选项只改变汉字和中文标点，英文字母与数字始终沿用默认字体。中文字体只在中文界面生效，切换其他语言时自动使用适合该语言的默认字体；切回中文恢复所选字体。字号对所有语言生效。这是设计稿演示；正式应用后续需按用户／设备持久保存，并在 RK3562 重启后恢复。当前不写入正式应用。')}
    <p class="u-settings-type-language-note">中文字体 · 其他语言随语言适配，字号通用</p>
    <div class="u-settings-type-label">字体<span>选择后立即应用</span></div>
    <div class="u-settings-fonts" role="group" aria-label="字体">${fontChoices.map(([id,name,note])=>`<button type="button" data-type-font="${id}" aria-pressed="${typographyState.font===id}"><strong class="u-settings-font-${id}">${name}</strong><small>${note}</small><span class="u-settings-font-check">${icon('check')}</span></button>`).join('')}</div>
    <div class="u-settings-type-label u-settings-size-label">字号</div>
    <div class="u-settings-sizes u-settings-segment" role="group" aria-label="字号">${sizeChoices.map(([id,name])=>`<button type="button" data-type-size="${id}" aria-pressed="${typographyState.size===id}">${name}</button>`).join('')}</div>
    </section>`;
  const updateTypography = shell => {
    if (!shell) return;
    shell.querySelectorAll('[data-type-font]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.typeFont===typographyState.font)));
    shell.querySelectorAll('[data-type-size]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.typeSize===typographyState.size)));
    window.KioskDesignTypography.apply();
  };
  // Design-only connection states; geometry is deliberately uncalibrated.
  const boardPreviewParams = new URLSearchParams(location.search);
  const boardPreview = {camera:boardPreviewParams.get('board-camera')!=='off',led:boardPreviewParams.get('board-led')!=='off'};
  const boardMissing = [!boardPreview.camera && '摄像头',!boardPreview.led && 'LED'].filter(Boolean);
  const boardAction = () => button('开始标定',boardMissing.length?'':'calib',`请先连接${boardMissing.join('和')}，再开始标定。`);
  const segment = (id,key) => `<span class="u-settings-segment" role="group" aria-label="${id}" data-setting-pref="${key}"><button type="button" aria-pressed="${preferences[key]}">开</button><button type="button" aria-pressed="${!preferences[key]}">关</button></span>`;
  const body = () => [
    `<section class="u-settings-section" data-group="board">${heading('实体棋盘','设计示意：摄像头、几何标定和 LED 分别显示状态。摄像头和 LED 都已连接即可开始标定；几何未标定不影响进入。')}
      <div class="u-settings-board-preview-note">设计示意</div>
      <div class="u-settings-board-status" aria-label="实体棋盘状态">
        <div><small>摄像头</small>${tag(boardPreview.camera?'已连接':'未连接',boardPreview.camera)}</div>
        <div><small>几何标定</small>${tag('未标定')}</div>
        <div><small>LED</small>${tag(boardPreview.led?'已连接':'未连接',boardPreview.led)}</div>
      </div>
      ${row('重新标定棋盘',boardAction(),boardMissing.length?'请先连接'+boardMissing.join('和'):'还没标定，可开始标定','u-settings-board-action')}</section>`,
    `<section class="u-settings-section" data-group="move">${heading('落子与提示','做对后自动进入下一题仅在训练营生效；出厂默认为开。')}
      ${row('做对后自动进入下一题',segment('做对后自动进入下一题','autoAdvance'))}</section>`,
    `<section class="u-settings-section" data-group="sound">${heading('声音','落子音效包括落子、提子及做题对错提示；语音提示只在用实体棋盘摆棋和做题时会响。两项独立设置。')}
      ${row('落子音效',segment('落子音效','sfx'))}
      ${row('语音提示',segment('语音提示','voice'))}</section>`,
    `<section class="u-settings-section" data-group="language">${heading('语言','当前仍在围棋设置中切换界面语言，未来将移至智星盒设置中心。')}
      ${row('界面语言',`<select class="u-settings-language" aria-label="界面语言">${[['cn','中文'],['en','English'],['tw','繁體中文'],['jp','日本語'],['ko','한국어'],['de','Deutsch'],['es','Español'],['fr','Français'],['ru','Русский'],['tr','Türkçe'],['ua','Українська']].map(([code,name])=>`<option value="${code}" ${preferences.language===code?'selected':''}>${name}</option>`).join('')}</select>`)}</section>`,
    typography(),
    `<section class="u-settings-section" data-group="about">${heading('关于','版本与本机、云端引擎状态均来自健康接口；此处为截图采集时的实机数值。')}
      ${row('版本',tag('1.17.1'))}
      ${row('本机 · KataGo',tag('可用',true))}
      ${row('云端 · KataGo',tag('没配置'))}</section>`,
  ].join('');
  const activeFor = id => ({settings:'board','settings-board':'board','settings-move':'move','settings-sound':'sound','settings-language':'language','settings-typography':'typography','settings-about':'about'})[id];
  const syncNav = scroll => {
    const shell = scroll.closest('.u-settings-shell');
    if (!shell) return;
    let selected = 'board';
    for (const [key] of sections) {
      const section = scroll.querySelector(`[data-group="${key}"]`);
      if (section && section.offsetTop <= scroll.scrollTop + 8) selected = key;
    }
    shell.querySelectorAll('.u-settings-nav nav button').forEach(button => {
      if (button.dataset.settingGroup === selected) button.setAttribute('aria-current','true');
      else button.removeAttribute('aria-current');
    });
  };
  function settings(s) {
    const active = activeFor(s.id);
    requestAnimationFrame(() => {
      const shell = document.querySelector(`.u-settings-shell[data-active="${active}"]`);
      updateTypography(shell);
      [['kaiti','Kiosk Preview Kaiti'],['lishu','Kiosk Preview Lishu'],['heiti','Kiosk Preview Heiti']].forEach(([id,family])=>{
        document.fonts.load(`22px "${family}"`,'汉字').catch(()=>[]).then(faces=>{
          if (!faces.length) {
            const option=shell?.querySelector(`[data-type-font="${id}"]`);
            if (option) {option.querySelector('small').textContent='本机未安装';option.title='本机未安装此字体，当前显示系统回退字形';}
          }
        });
      });
      const scroll = shell?.querySelector('.u-settings-scroll');
      const section = scroll?.querySelector(`[data-group="${active}"]`);
      if (scroll && section) {scroll.scrollTop = section.offsetTop;syncNav(scroll);}
    });
    return `<div class="u-settings-shell" data-active="${active}">
      <aside class="u-settings-nav"><div class="u-settings-nav-head"><strong>设置</strong><span>Settings</span></div><nav aria-label="设置分组">${sections.map(([key,label,glyph,target])=>`<button type="button" data-setting-group="${key}" data-switch="${target}" ${active===key?'aria-current="true"':''}>${icon(glyph)}<span>${label}</span></button>`).join('')}</nav></aside>
      <main class="u-settings-scroll" aria-label="设置内容"><div class="u-settings-stack">${body()}</div></main>
    </div>`;
  }
  ['settings','settings-board','settings-move','settings-sound','settings-language','settings-typography','settings-about'].forEach(id => F[id] = settings);

  F.calib = () => `<div class="u-settings-calib"><div class="u-settings-calib-pagebar"><button class="u-settings-back" type="button" data-switch="settings-board">${icon('arrow')}返回设置</button><strong>棋盘标定</strong>${help('标定前先把盘清空。定位四角和天元共 5 个点；LED 只在你按下开始后才会亮，不会自动点亮。')}<div class="u-settings-calib-views"><button class="is-active" type="button" data-view="raw">原始画面</button><button type="button" data-view="warped">俯视矫正</button></div></div>
    <div class="u-settings-calib-main"><div class="u-settings-calib-camera"><span data-camera-text>画面重连中…</span><div class="u-settings-calib-camera-foot"><span>四角 + 天元 · 共 5 个定位点</span><strong>第 1 / 4 步</strong></div></div><div class="u-settings-calib-rail"><div class="u-settings-calib-status"><div><small>摄像头</small><strong>未连接</strong></div><div><small>标定</small><strong>未标定</strong></div><div><small>LED</small><strong>未连接</strong></div></div><div class="u-settings-calib-steps">${['等待棋盘稳定','确认并锁定曝光','定位棋盘','生成空盘基线'].map((step,i)=>`<div class="${i===0?'is-current':''}"><span>${i+1}</span><strong>${step}</strong><small>${i===0?'进行中':'未开始'}</small></div>`).join('')}</div><div class="u-settings-calib-alert">LED 只在按下开始后才亮${help('按下后才自动点亮 LED 并拍摄 5 个定位点。失败时显示具体诊断，常见原因包括棋子压住星位、灯太暗，或摄像头被挪过。')}</div><button class="u-settings-calib-start" type="button" disabled aria-label="重新开始标定，摄像头与 LED 未连接">重新开始标定 · 设备未连接</button></div></div></div>`;

  F.login = (s,ctx) => {
    const art = `url('${ctx.root+s.current}')`;
    const cards = [['围棋','GO','play'],['国际象棋','CHESS',null],['中国象棋','XIANGQI',null],['五子棋','GOMOKU',null]];
    return `<div class="u-settings-launcher"><div class="u-settings-launcher-top"><span class="u-settings-launcher-logo" style="background-image:${art}"></span><div class="u-settings-launcher-brand"><strong>智星盒</strong><em>StellaBox</em></div><div class="u-settings-launcher-spacer"></div><span class="u-settings-launcher-current"><i></i>当前：围棋对弈</span><span class="u-settings-launcher-user"><i>F</i>fan</span><button type="button" data-help="盒端退出登录由智星盒启动门户管理。设计预览不会修改设备账户。">退出登录</button><button class="u-settings-launcher-gear" type="button" aria-label="智星盒设置" data-help="这是智星盒启动门户的设置入口，与围棋模块内的设置不同。">${icon('settings')}</button></div><div class="u-settings-launcher-cards">${cards.map(([name,en,target],i)=>`<button type="button" class="u-settings-launcher-card ${i===0?'is-current':''}" ${target?`data-switch="${target}"`:`data-help="设计预览：${name}属智星盒其他应用，当前 HTML 仅展示启动门户现状。"`}><span class="u-settings-launcher-art u-settings-launcher-art-${i}" style="background-image:${art}"></span><span class="u-settings-launcher-card-label"><strong>${name}</strong><small>${en}</small><i></i></span></button>`).join('')}</div><div class="u-settings-launcher-agent"><span class="u-settings-launcher-agent-mark" style="background-image:${art}"></span><div><strong>Hermes Agent</strong><span>智能体 · 在线</span><p>住进你消息应用里的私人 AI 智能体</p><p>有长期记忆、能定时办事、接入任意大模型</p></div>${help('Hermes Agent 是智星盒启动门户上的智能体应用：住进你的消息应用，具有长期记忆、可定时办事，并接入任意大模型。当前围棋设计稿不修改该应用。')}<button type="button" data-help="这是启动门户上的 Hermes Agent 入口；围棋改版不修改该应用。">轻触进入 ${icon('next')}</button></div></div>`;
  };

  document.addEventListener('click', e => {
    const font = e.target.closest('[data-type-font]');
    const size = e.target.closest('[data-type-size]');
    if (font || size) {
      if (font) window.KioskDesignTypography.set({font:font.dataset.typeFont});
      if (size) window.KioskDesignTypography.set({size:size.dataset.typeSize});
      updateTypography((font || size).closest('.u-settings-shell'));
    }
    const seg = e.target.closest('.u-settings-segment[data-setting-pref] button');
    if (seg) {
      preferences[seg.parentElement.dataset.settingPref] = seg.textContent.trim() === '开';
      seg.parentElement.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed',String(button===seg)));
    }
    const view = e.target.closest('.u-settings-calib-views button');
    if (view) {
      view.parentElement.querySelectorAll('button').forEach(button=>button.classList.toggle('is-active',button===view));
      const label = document.querySelector('.u-settings-calib-camera [data-camera-text]');
      if (label) label.textContent = view.dataset.view === 'warped' ? '完成 LED 标定后生成俯视画面' : '画面重连中…';
    }
  }, true);
  document.addEventListener('change', e => {
    if (e.target.matches('.u-settings-language')) {
      preferences.language = e.target.value;
      window.KioskDesignTypography.set({language:e.target.value});
      updateTypography(e.target.closest('.u-settings-shell'));
    }
  }, true);
  document.addEventListener('scroll', e => {
    if (e.target.matches?.('.u-settings-scroll')) syncNav(e.target);
  }, true);
})();
