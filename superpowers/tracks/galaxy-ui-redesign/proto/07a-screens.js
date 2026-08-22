/* ═══════════════════════════════════════════════════════════════
   SCREEN REGISTRY
   Every screen reproduces the page AS IT IS TODAY on
   feature/galaxy-style-unify (develop b727e721) — defects included.
   Two pages are already on the approved template and are marked so.
   ═══════════════════════════════════════════════════════════════ */
const SCREENS = [];

const NOW = { black: '陈泓明', white: '姚钧耀', event: '天元记谱-2603211856' };

/* legacy pages ask for height:100vh inside a shell that is
   (viewport − 52px) tall. Reproduced, and labelled. */
const VH = `<div class="vhwarn">页面根节点 height:100vh · 比可用高度多 52px</div>`;

/* ───────────────────────────── 首页 ───────────────────────────── */
SCREENS.push({
  id: 'dashboard', group: '首页', label: '首页 · 模块入口', route: '/galaxy',
  nav: 'home', kind: 'content',
  render() {
    const mods = [
      ['对局', '与AI或其他玩家对弈', 'SportsEsports', '/galaxy/play', false],
      ['研究', '分析棋局与研究变化', 'Science', '/galaxy/research', false],
      ['复盘', '生成AI复盘报告', 'Assessment', '/galaxy/report', false],
      ['直播', '观看职业对局直播', 'LiveTv', '/galaxy/live', false],
      ['死活题', '练习死活与手筋', 'Extension', '/galaxy/tsumego', false],
    ];
    return {
      html: `<div data-zone="body">
        <div style="margin-bottom:48px">
          <h1 style="font-size:3rem;font-weight:800;margin:0 0 8px;line-height:1.2;background:linear-gradient(45deg,#4a6b5c 30%,#5d8270 90%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:#5d8270">欢迎使用智星盒</h1>
          <p style="font-size:1.25rem;color:var(--tx2);margin:0">您的专业围棋训练与分析平台。</p>
        </div>
        <div class="gridcards" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:32px">
          ${mods.map(([t, d, i, p]) => card(
            `<div style="padding:24px;height:100%">
               <div style="width:56px;height:56px;border-radius:16px;background:var(--jade-d);display:grid;place-items:center;margin-bottom:16px;color:#eaf3ee">${icon(i)}</div>
               <div style="font-size:1.5rem;font-weight:700;margin-bottom:8px">${t}</div>
               <div style="font-size:.875rem;color:var(--tx2)">${d}</div>
             </div>`,
            { act: '导航 ' + p, src: 'Dashboard.tsx:20-40' })).join('')}
        </div>
      </div>`,
    };
  },
  note: `<h3>根级内容页</h3>
    <p>今天的页头是一个 <code>h3</code> 渐变标题加一行 <code>h6</code> 副标题（<code>Dashboard.tsx:81-88</code>）。
    按 spec §2.4，根级页面页头<b>只留标题</b>、没有上一级；副标题「您的专业围棋训练与分析平台。」属于长副标题，
    要下沉到正文首个业务区，不能删。</p>
    <p>另外这页的外层是 <code>p:6, overflow:auto</code> 但没有 <code>flex:1 / minHeight:0</code>，
    在矮视口下内容会被 <code>.galaxy-root</code> 的 <code>overflow:hidden</code> 裁掉且没有滚动条。
    scope 说内容页<b>不动承重结构</b>，所以这条只记录、本轮不改。</p>`,
});

/* ───────────────────────────── 对局 ───────────────────────────── */
SCREENS.push({
  id: 'play-menu', group: '对局', label: '对局 · 模式选择', route: '/galaxy/play',
  nav: 'play', kind: 'content',
  render() {
    const opts = [
      ['自由对弈', '练习模式，支持完整分析、悔棋和自定义设置。', 'SmartToy', '/galaxy/play/ai?mode=free'],
      ['升降级对局', '与拟人AI进行排位赛。对局中无分析功能。', 'SportsEsports', '/galaxy/play/ai?mode=rated'],
      ['人人对弈', '挑战好友或在线匹配对手。', 'Person', '/galaxy/play/human'],
    ];
    return {
      html: `<div data-zone="body" style="max-width:1200px;margin:0 auto">
        <div class="rowbetween" style="align-items:flex-start;flex-wrap:wrap;margin-bottom:48px">
          <div>
            <h1 style="font-size:2.125rem;font-weight:700;margin:0 0 8px">对局</h1>
            <p style="font-size:1rem;color:var(--tx2);margin:0">选择游戏模式</p>
          </div>
          ${btn({ label: '对局记录', variant: 'outlined', color: 'inherit', act: '导航 /galaxy/report', src: 'PlayMenu.tsx:47' })}
        </div>
        <div class="gridcards" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:32px">
          ${opts.map(([t, d, i, p]) => card(
            `<div style="padding:32px 16px;text-align:center;display:flex;flex-direction:column;align-items:center;gap:16px;height:100%">
               <div style="color:var(--jade-l)"><svg class="ic" style="width:60px;height:60px"><use href="#i-${i}"/></svg></div>
               <div><div style="font-size:1.25rem;font-weight:700;margin-bottom:8px">${t}</div>
               <div style="font-size:.875rem;color:var(--tx2)">${d}</div></div>
             </div>`,
            { act: '导航 ' + p, src: 'PlayMenu.tsx:62-100', style: 'border-radius:16px' })).join('')}
        </div>
      </div>`,
    };
  },
  note: `<h3>根级内容页 · 页头已有右侧动作</h3>
    <p>这页的页头已经是「左标题 + 右按钮」的单行结构（<code>PlayMenu.tsx:41-55</code>），
    最接近目标形态。要动的只有：副标题「选择游戏模式」下沉，右边的「对局记录」不是返回按钮而是页面动作 ——
    spec §2.4 说页头右侧放的是<b>返回上一级</b>，所以「对局记录」得挪进正文。</p>
    <p>⚠️ <code>tests/galaxy-play-record-entry-visual.spec.ts:61</code> 断言
    <code>getByRole('heading', { name: '对局', exact: true })</code>，标题字符串不能改。</p>`,
});

SCREENS.push({
  id: 'ai-setup-rated', group: '对局', label: '升降级对弈 · 设置（已在模板上）', route: '/galaxy/play/ai?mode=rated',
  nav: 'play', kind: 'content',
  branches: [
    { id: 'ready', label: '可开新局' }, { id: 'blocking', label: '有一局挡着' },
    { id: 'receipt', label: '结算回执' }, { id: 'pending', label: '成绩未送达' },
    { id: 'loading', label: '加载中' }, { id: 'error', label: '状态加载失败' },
  ],
  dialogs: {
    displace: `<div class="dlg" data-zone="dialog">
      <h3>认输那一局？</h3>
      <p>那一局已经在棋盘上开起来了。认输会按输一局记进升降级。</p>
      <div class="acts">
        ${btn({ label: '取消', color: 'inherit', act: '关闭弹窗，什么都不发', src: 'AiLadderRatedSetup.tsx:492' })}
        <button class="mbtn contained warn" data-act="POST /api/v1/ai-ladder/games/{id}/end" data-src="AiLadderRatedSetup.tsx:520" style="background:var(--warn);color:#2a1a04">确认认输</button>
      </div></div>`,
  },
  render(b) {
    const ladder = (right) => `<div data-zone="body">
      ${cph({ title: '升降级对弈', parentLabel: '对局', parentTo: '/galaxy/play', src: 'AiSetupPage.tsx:454' })}
      <div class="card" style="margin-top:20px;display:grid;grid-template-columns:minmax(0,1fr) 372px;overflow:hidden;border-radius:14px">
        <div style="padding:32px;min-height:520px;display:flex;flex-direction:column;gap:28px">
          <div>
            <p class="sec-label">当前段位</p>
            <div class="inline" style="gap:16px;align-items:baseline">
              <b style="font-size:3rem;font-family:var(--mono);line-height:1">${b === 'receipt' ? '2K' : '3K'}</b>
              <span class="dim" style="font-size:.8rem">41 阶棋力体系 · 第 18 阶</span>
            </div>
          </div>
          <div>
            <p class="sec-label">最近5盘 <span class="dim" style="text-transform:none;letter-spacing:0">只统计升降级对弈</span></p>
            <div class="inline" style="gap:6px">
              ${['胜', '胜', '负', '胜', '负'].map((r, i) => `<span class="chip ${r === '胜' ? 'ok' : 'err'}" title="第${i + 1}盘">${r}</span>`).join('')}
            </div>
          </div>
          <div>
            <p class="sec-label">累计净胜分</p>
            <div class="inline" style="gap:12px">
              <span class="mono" style="font-size:1.5rem;color:var(--ok)">+1</span>
              <span class="dim" style="font-size:.78rem">当前累计净胜分+1，正值朝升段方向，达到+3升段</span>
            </div>
            <div style="height:6px;border-radius:3px;background:rgba(255,255,255,.08);margin-top:10px;overflow:hidden">
              <div style="width:66%;height:100%;background:var(--jade-l)"></div>
            </div>
            <div class="rowbetween dim" style="font-size:.7rem;margin-top:5px"><span>降段 -3</span><span>升段 +3</span></div>
          </div>
          <div style="margin-top:auto">
            <p class="sec-label">本局固定设置</p>
            <p class="muted" style="margin:0;font-size:.85rem">19 路 · 中国规则 · 贴 7.5 目 · 不让子</p>
          </div>
        </div>
        <div style="padding:32px;border-left:1px solid var(--line);display:flex;flex-direction:column;background:rgba(0,0,0,.18)" data-zone="right-rail-middle">
          ${right}
        </div>
      </div>
    </div>`;

    if (b === 'loading') {
      return {
        html: `<div data-zone="body">${cph({ title: '升降级对弈', parentLabel: '对局', parentTo: '/galaxy/play', src: 'AiSetupPage.tsx:454' })}
          <div class="card" style="margin-top:20px;padding:32px;display:grid;grid-template-columns:minmax(0,1fr) 372px;gap:32px">
            <div class="stack g16"><div class="skel" style="height:64px"></div><div class="skel" style="height:40px"></div><div class="skel" style="height:120px"></div></div>
            <div class="stack g16"><div class="skel" style="height:180px"></div><div class="skel" style="height:54px"></div></div>
          </div>
          <p class="dim" style="margin-top:14px;font-size:.85rem">正在读取你的段位…</p></div>`,
      };
    }
    if (b === 'error') {
      return {
        html: `<div data-zone="body">${cph({ title: '升降级对弈', parentLabel: '对局', parentTo: '/galaxy/play', src: 'AiSetupPage.tsx:454' })}
          <div class="alert error" style="margin-top:20px">升降级对弈状态加载失败</div>
          <div style="margin-top:14px">${btn({ label: '重试', variant: 'outlined', act: '重新 GET /api/v1/ai-ladder/status', src: 'AiLadderRatedSetup.tsx' })}</div></div>`,
      };
    }
    if (b === 'blocking') {
      return {
        html: ladder(`<p class="sec-label">未完成对局</p>
          <div class="inline" style="gap:12px;margin-bottom:6px">
            <span class="kstone b" style="width:34px;height:34px"></span>
            <div><div style="font-weight:600">智星棋手</div><div class="mono dim" style="font-size:.8rem">5K</div></div>
          </div>
          <div class="inline" style="margin-bottom:20px">
            <span class="chip warn">对局中</span><span class="chip">当前设备</span>
          </div>
          <div class="stack g12" style="margin-top:auto">
            ${btn({ label: '继续对局', variant: 'contained', size: 'lg', full: true, act: '导航 /galaxy/play/game/{sessionId}?mode=rated', src: 'AiLadderRatedSetup.tsx' })}
            ${btn({ label: '立即重试', variant: 'outlined', full: true, act: 'POST /api/v1/ai-ladder/games/{id}/settlement/retry', src: 'AiLadderRatedSetup.tsx' })}
            ${dlgOpen('displace', '认输那一局，在这里开新局', { variant: 'outlined', color: 'warn', src: 'AiLadderRatedSetup.tsx:470' })}
          </div>`),
      };
    }
    if (b === 'pending') {
      return {
        html: ladder(`<p class="sec-label">未完成对局</p>
          <div style="margin:auto 0;text-align:center;padding:40px 0">
            <p style="margin:0 0 10px;font-size:1.5rem;line-height:1.5">这一局已经下完，成绩还没送到云端。</p>
            <div class="alert warning" style="margin-top:14px;text-align:left">暂时无法确认本局状态，请重试</div>
          </div>
          <div style="margin-top:auto">
            ${btn({ label: '刷新状态', variant: 'contained', size: 'lg', full: true, act: 'handleLifecycleRetry() → 重新 GET /api/v1/ai-ladder/status', src: 'AiLadderRatedSetup.tsx' })}
          </div>`),
      };
    }
    if (b === 'receipt') {
      return {
        html: ladder(`<p class="sec-label">本局挑战</p>
          <div style="margin:auto 0;text-align:center;padding:48px 0">
            <div style="color:var(--ok);margin-bottom:12px">${icon('CheckCircle')}</div>
            <div style="font-size:1.1rem;font-weight:600;margin-bottom:6px">结算已完成</div>
            <p class="muted" style="margin:0;font-size:.85rem">本局已计入升降级 · 净胜 +3，升一档，计数归零。</p>
          </div>`),
      };
    }
    return {
      html: ladder(`<p class="sec-label">本局挑战</p>
        <div class="inline" style="gap:12px;margin-bottom:8px">
          <span class="kstone b" style="width:34px;height:34px"></span>
          <div><div style="font-weight:600">智星棋手</div><div class="mono dim" style="font-size:.8rem">3K · 已认证</div></div>
        </div>
        <span class="chip ok">可挑战</span>
        <div style="margin-top:26px">
          <p class="sec-label">选择执子</p>
          <div class="inline" style="gap:8px">
            <button class="tbtn" role="button" aria-pressed="true" data-toggle="ladderB" data-act="setColor('B') → /start color:'black'" data-src="AiLadderRatedSetup.tsx"><span class="kstone b"></span>黑棋</button>
            <button class="tbtn" role="button" aria-pressed="false" data-toggle="ladderW" data-act="setColor('W') → /start color:'white'" data-src="AiLadderRatedSetup.tsx"><span class="kstone w"></span>白棋</button>
          </div>
        </div>
        <div style="margin-top:auto;padding-top:32px" data-zone="right-rail-actions">
          ${btn({ label: '开始正式对局', variant: 'contained', size: 'lg', full: true, act: 'POST /api/v1/ai-ladder/start', src: 'AiLadderRatedSetup.tsx' })}
        </div>`),
    };
  },
  note: `<h3>已迁移 · 内容页样板</h3>
    <p>这是 <code>ContentPageHeader</code> 的<b>照抄对象</b>：单行左右，左「升降级对弈」右「← 对局」
    （<code>AiSetupPage.tsx:454</code>）。12 个内容页要变成这个样子。</p>
    <p>注意：<code>AiSetupPage</code> 只有 <code>isRated</code> 这一支在模板上，
    自由对弈那一支（下一个页面）还是老样子。scope 说别改这个文件，所以这条不一致本轮保留。</p>`,
});

SCREENS.push({
  id: 'ai-setup-free', group: '对局', label: '自由对弈 · 设置（大表单）', route: '/galaxy/play/ai?mode=free',
  nav: 'play', kind: 'content',
  branches: [{ id: 'ok', label: '就绪' }, { id: 'loading', label: '加载中' }],
  render(b) {
    if (b === 'loading') return { html: `<div data-zone="body" style="padding:32px">Loading...</div>` };
    const sel = (label, opts, src) => `<div style="margin-bottom:18px">
      <label class="flabel">${label}</label>
      <div class="selwrap"><select class="sel" aria-label="${label}" data-act="set${label}" data-src="${src}">
        ${opts.map(o => `<option>${o}</option>`).join('')}</select>${icon('ArrowDropDown', 'sm')}</div></div>`;
    const sld = (label, val, min, max, step, src) => `<div style="margin-bottom:18px">
      <label class="flabel">${label}: <span class="mono">${val}</span></label>
      <input class="slider" type="range" min="${min}" max="${max}" step="${step}" value="${val}" aria-label="${label}" data-act="set${label}" data-src="${src}"></div>`;
    return {
      html: `<div data-zone="body" style="max-width:1000px;margin:0 auto">
        <h1 style="font-size:2.125rem;font-weight:700;margin:0 0 24px">自由对弈设置</h1>
        <div class="gridcards" style="grid-template-columns:1fr 1fr;gap:32px">
          <div class="card" style="padding:32px;border-radius:16px">
            <h2 style="font-size:1.25rem;font-weight:600;margin:0 0 20px">棋盘与规则</h2>
            ${sel('棋盘大小', ['19x19 (标准)', '13x13', '9x9'], 'AiSetupPage.tsx:512')}
            ${sel('规则', ['日本', '中国', '韩国', 'AGA', 'New Zealand', 'Tromp-Taylor'], 'AiSetupPage.tsx:523')}
            ${sel('执子颜色', ['黑棋 (先手)', '白棋 (后手)'], 'AiSetupPage.tsx:536')}
            ${sld('让子', 0, 0, 9, 1, 'AiSetupPage.tsx:548')}
            ${sld('贴目', 6.5, 0.5, 85.5, 0.25, 'AiSetupPage.tsx:556')}
          </div>
          <div class="card" style="padding:32px;border-radius:16px">
            <h2 style="font-size:1.25rem;font-weight:600;margin:0 0 20px">对手与时间</h2>
            ${sel('AI选点方式', ['KataGo', '拟人', '历史棋风', '棋力阶梯', '校准级别', 'KataHandicap', '简单地域', '目数损失', '策略', '加权', '和棋', '反模仿', '策略选择', '局部', '脱先', '实地', '外势'], 'AiSetupPage.tsx:568')}
            ${sld('段位', 10, 0, 28, 1, 'AiSetupPage.tsx:590')}
            <div style="padding:14px;border:1px solid var(--line);border-radius:10px;margin-bottom:18px">
              <p class="sec-label">AI设置</p>
              <div style="margin-bottom:14px">
                <label class="flabel">棋力等级</label>
                <div class="selwrap"><select class="sel" aria-label="棋力等级" data-act="setLadderRung(rung) → 开局传 ladder_rung" data-src="AiSetupPage.tsx:600">
                  ${['20K', '19K', '18K', '17K', '16K', '15K', '10K', '5K', '3K', '1K', '1D', '3D', '5D', '7D', '9D'].map(r => `<option ${r === '3K' ? 'selected' : ''}>${r}</option>`).join('')}
                </select>${icon('ArrowDropDown', 'sm')}</div>
              </div>
              <label class="swrow" style="padding:2px 0"><span>modern_style</span>
                <input type="checkbox" aria-label="modern_style" data-act="handleSettingChange('modern_style', checked) → 500ms 防抖后 POST /api/ai/estimate-rank" data-src="AiSetupPage.tsx:614" style="width:18px;height:18px;accent-color:var(--jade)"></label>
              <div style="margin:12px 0">
                <label class="flabel">strength <span class="mono dim">kyu 5</span></label>
                <input class="slider" type="range" min="0" max="8" value="4" aria-label="strength" data-act="索引滑块 → handleSettingChange(key, values[index])" data-src="AiSetupPage.tsx:620">
              </div>
              <div>
                <label class="flabel">pro_year</label>
                <input class="field" value="2015" aria-label="pro_year" data-act="handleSettingChange(key, value) — TextField 兜底分支" data-src="AiSetupPage.tsx:632">
              </div>
            </div>
            <hr class="hr" style="margin:24px 0">
            ${swrow({ id: 'timer', label: '启用计时器', on: false, src: 'AiSetupPage.tsx:640' })}
            ${sld('保留时间 (分钟)', 10, 0, 60, 1, 'AiSetupPage.tsx:652')}
            ${sld('每步读秒时间 (秒)', 30, 5, 60, 5, 'AiSetupPage.tsx:660')}
            ${sld('读秒次数', 3, 1, 10, 1, 'AiSetupPage.tsx:668')}
          </div>
        </div>
        <div class="inline" style="justify-content:flex-end;gap:16px;margin-top:32px">
          ${btn({ label: '取消', color: 'inherit', act: '导航 /galaxy/play（不经 GameNavigationContext）', src: 'AiSetupPage.tsx:684' })}
          ${btn({ label: '对局', variant: 'contained', size: 'lg', act: 'POST /api/session → POST /api/newgame', src: 'AiSetupPage.tsx:690' })}
        </div>
      </div>`,
    };
  },
  note: `<h3>同一个文件里的另一半</h3>
    <p><code>AiSetupPage.tsx</code> 的 <code>isRated</code> 分支已经在模板上，这个 free 分支没有：
    标题是裸 <code>h4</code>，没有 <code>ContentPageHeader</code>，也没有返回上一级。</p>
    <p>scope 把 <code>AiSetupPage.tsx</code> 列为「照抄对象，别改它们」，
    所以这半边本轮<b>不动</b> —— 这是一个已知的、会被本轮留下的不一致，需要你裁定要不要一起收掉。</p>`,
});

/* ───────────────────────────── 研究 ───────────────────────────── */
const researchRail = (mode) => {
  const tool = (id, label, icon2, on) => tbtn({ id, label, icon: icon2, on, src: 'ResearchToolbar.tsx' });
  return `<div style="padding:16px" data-zone="right-rail-top">
      <p class="sec-label">对局信息</p>
      <div class="stack g8">
        <div><label class="flabel">黑方</label><input class="field" value="黑方" aria-label="黑方" data-act="board.setPlayerBlack" data-src="ResearchSetupPanel.tsx"></div>
        <div><label class="flabel">白方</label><input class="field" value="白方" aria-label="白方" data-act="board.setPlayerWhite" data-src="ResearchSetupPanel.tsx"></div>
        <div class="inline" style="gap:10px">
          <div style="flex:1"><label class="flabel">棋盘大小</label><div class="selwrap"><select class="sel" aria-label="棋盘大小" data-act="board.setBoardSize" data-src="ResearchSetupPanel.tsx"><option>19×19</option><option>13×13</option><option>9×9</option></select>${icon('ArrowDropDown', 'sm')}</div></div>
          <div style="flex:1"><label class="flabel">规则</label><div class="selwrap"><select class="sel" aria-label="规则" data-act="board.setRules" data-src="ResearchSetupPanel.tsx"><option>中国规则</option><option>日本规则</option><option>韩国规则</option></select>${icon('ArrowDropDown', 'sm')}</div></div>
        </div>
        <div class="inline" style="gap:10px">
          <div style="flex:1"><label class="flabel">贴目</label><input class="field" type="number" step="0.5" value="7.5" aria-label="贴目" data-act="board.setKomi" data-src="ResearchSetupPanel.tsx"></div>
          <div style="flex:1"><label class="flabel">让子</label><div class="selwrap"><select class="sel" aria-label="让子" data-act="board.setHandicap" data-src="ResearchSetupPanel.tsx"><option>无</option><option>2子</option><option>3子</option><option>4子</option><option>5子</option><option>6子</option></select>${icon('ArrowDropDown', 'sm')}</div></div>
        </div>
      </div>
    </div>
    <hr class="hr">
    <div style="padding:16px" data-zone="right-rail-middle">
      <p class="sec-label">编辑工具</p>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px">
        ${tool('r-num', '手数', 'FormatListNumbered')}
        ${tool('r-pass', '停一手', 'PanToolAlt')}
        ${tool('r-move', '移动', 'OpenWith')}
        ${tbtn({ id: 'r-del', label: '删除', icon: 'DeleteForever', cls: 'danger', src: 'ResearchToolbar.tsx:191' })}
        ${tool('r-black', '摆黑', STONE.b)}
        ${tool('r-white', '摆白', STONE.w)}
        ${tool('r-alt', '交替', STONE.alt, true)}
        ${tool('r-clear', '清空', 'LayersClear')}
        ${tool('r-hint', '建议', 'TipsAndUpdates')}
        ${tool('r-terr', '领地', 'Map')}
      </div>
      <div class="inline" style="gap:8px;margin-top:14px">
        ${dlgOpen('openmenu', '打开', { variant: 'outlined', icon: 'FolderOpen', src: 'ResearchToolbar.tsx' })}
        ${dlgOpen('savemenu', '保存', { variant: 'outlined', icon: 'Save', src: 'ResearchToolbar.tsx' })}
      </div>
    </div>
    ${mode === 'l3' ? `<hr class="hr"><div style="padding:16px" data-zone="right-rail-middle">
      <p class="sec-label">AI 推荐</p>
      <table style="width:100%;border-collapse:collapse;font-size:.8rem">
        <thead><tr style="color:var(--tx3);text-align:left"><th style="font-weight:500;padding:4px 0">着手</th><th style="font-weight:500">胜率</th><th style="font-weight:500">目差</th><th style="font-weight:500">推荐度</th></tr></thead>
        <tbody class="mono">
          <tr><td style="padding:4px 0">Q16</td><td>54.2%</td><td>+1.8</td><td>92%</td></tr>
          <tr><td style="padding:4px 0">D4</td><td>52.9%</td><td>+0.9</td><td>61%</td></tr>
          <tr><td style="padding:4px 0">R5</td><td>51.1%</td><td>+0.2</td><td>34%</td></tr>
        </tbody></table>
      <div class="tabs" style="margin:12px -16px 0">
        <button role="tab" aria-selected="true" data-act="切到 走势图" data-src="ResearchAnalysisPanel.tsx">走势图</button>
        <button role="tab" aria-selected="false" data-act="切到 妙手 (2)" data-src="ResearchAnalysisPanel.tsx">妙手 (2)</button>
        <button role="tab" aria-selected="false" data-act="切到 问题手 (5)" data-src="ResearchAnalysisPanel.tsx">问题手 (5)</button>
      </div>
      <div class="stack g4" style="margin-top:12px">
        ${[57, 88, 121].map(n => `<button class="rowbetween" data-act="onMoveClick(${n}) → setCurrentMove(${n})" data-src="ResearchAnalysisPanel.tsx"
          style="width:100%;background:none;border:0;border-left:3px solid var(--ok);padding:6px 10px;color:inherit;font:inherit;cursor:pointer;text-align:left">
          <span style="font-size:.82rem">第${n}手 Q16</span><span class="mono" style="font-size:.78rem;color:var(--ok)">+6.2</span></button>`).join('')}
      </div>
    </div>` : ''}`;
};

SCREENS.push({
  id: 'research', group: '研究', label: '研究 · 摆盘 / 分析', route: '/galaxy/research',
  nav: 'research', kind: 'content',
  branches: [{ id: 'l1', label: 'L1 编辑' }, { id: 'l2', label: 'L2 分析中' }, { id: 'l3', label: 'L3 分析结果' }, { id: 'lib', label: '棋谱库弹窗' }],
  dialogs: {
    openmenu: `<div class="dlg" style="max-width:280px" data-zone="dialog"><h3>打开</h3>
      <div style="padding:0 8px 12px">
        <button class="navitem" data-act="board.openLocalSGF() → 隐藏 file input" data-src="ResearchToolbar.tsx">${icon('UploadFile')}<span>打开本地 SGF</span></button>
        <button class="navitem" data-act="setLibraryOpen(true) → 棋谱库弹窗" data-src="ResearchToolbar.tsx">${icon('LibraryBooks')}<span>从棋谱库导入</span></button>
      </div>
      <div class="acts">${btn({ label: '关闭', color: 'inherit', act: '关闭菜单' })}</div></div>`,
    savemenu: `<div class="dlg" style="max-width:280px" data-zone="dialog"><h3>保存</h3>
      <div style="padding:0 8px 12px">
        <button class="navitem" data-act="board.saveLocalSGF() → Blob 下载" data-src="ResearchToolbar.tsx">${icon('Save')}<span>保存 SGF</span></button>
        <button class="navitem" data-act="UserGamesAPI.create(source:'research')" data-src="ResearchToolbar.tsx">${icon('CloudUpload')}<span>保存到棋谱库</span></button>
        <button class="navitem" data-act="navigator.clipboard.writeText(sgf)" data-src="ResearchToolbar.tsx">${icon('ContentCopy')}<span>复制 SGF 到剪贴板</span></button>
      </div>
      <div class="acts">${btn({ label: '关闭', color: 'inherit', act: '关闭菜单' })}</div></div>`,
    pass: `<div class="dlg" data-zone="dialog"><h3>停一手</h3>
      <p>确认在当前位置插入一个 Pass（停一手）？</p>
      <div class="acts">${btn({ label: '取消', color: 'inherit', size: 'sm', act: 'setPassConfirmOpen(false)', src: 'ResearchToolbar.tsx:295' })}
      ${btn({ label: '确认', variant: 'contained', size: 'sm', act: 'board.handlePass()', src: 'ResearchToolbar.tsx:302' })}</div></div>`,
  },
  render(b, vp) {
    if (b === 'l2') {
      return {
        raw: `<div class="lrow vh100" style="justify-content:center;align-items:center" data-zone="body">
          <div style="text-align:center;width:400px">
            <div style="color:var(--jade-l);margin:0 auto 16px;width:48px"><svg class="ic" style="width:48px;height:48px"><use href="#i-Science"/></svg></div>
            <div style="font-size:1.25rem;font-weight:600;margin-bottom:8px">正在分析棋局</div>
            <p class="muted" style="margin:0 0 24px;font-size:.9rem">已完成 128 / 250 步</p>
            <div style="margin:0 16px 8px;height:10px;border-radius:5px;background:rgba(255,255,255,.1);overflow:hidden">
              <div style="width:51%;height:100%;background:var(--jade);border-radius:5px"></div></div>
            <div class="mono" style="color:var(--jade-l);font-weight:700">51%</div>
            <div class="mono dim" style="font-size:.85rem;margin-top:4px">预计剩余 2分14秒</div>
            <div style="margin-top:14px">${btn({ label: '取消', color: 'err', size: 'sm', act: 'handleReturnToEdit() → 回到 L1', src: 'ResearchPage.tsx:561' })}</div>
          </div>${VH}</div>`,
      };
    }
    if (b === 'lib') {
      return {
        raw: `<div class="lrow vh100" data-zone="body">
          <div class="lmain"><div class="lboard"><canvas class="boardcv" data-floor="400" data-board='${esc(JSON.stringify({ stones: demoStones(12), coords: true }))}'></canvas></div></div>
          <div class="lrail w500"></div>
          <div class="scrim" style="position:absolute">
            <div class="dlg" style="max-width:720px" data-zone="dialog">
              <h3>棋谱库</h3>
              <div class="tabs" style="padding:0 22px">
                <button role="tab" aria-selected="true" data-act="切到 我的棋谱" data-src="CloudSGFPanel.tsx">我的棋谱</button>
                <button role="tab" aria-selected="false" data-act="切到 我的盘面" data-src="CloudSGFPanel.tsx">我的盘面</button>
                <button role="tab" aria-selected="false" data-act="切到 大赛棋谱" data-src="CloudSGFPanel.tsx">大赛棋谱</button>
              </div>
              <div style="padding:14px 22px 0">
                <div class="fieldwrap">${icon('Search', 'sm')}
                  <input class="field" placeholder="搜索棋手、赛事..." aria-label="搜索棋手、赛事" data-act="过滤棋谱列表" data-src="CloudSGFPanel.tsx"></div>
              </div>
              <div style="padding:16px 22px;max-height:320px;overflow:auto" class="stack g8">
                ${[['柯洁', '朴廷桓', 250], ['申真谞', '芈昱廷', 211], ['陈泓明', '姚钧耀', 194]].map(([a, c, m] ) => `
                  <button class="kcard" data-act="加载该棋谱到研究盘面" data-src="CloudSGFPanel.tsx">
                    <div class="kmeta"><span>2026-08-12</span><span class="chip" style="height:18px;font-size:.62rem">${m}手</span></div>
                    <div class="kplayers"><span class="side"><i class="kstone b"></i>${a}</span><span class="dim">vs</span><span class="side w">${c}<i class="kstone w"></i></span></div>
                  </button>`).join('')}
              </div>
              <div class="acts">${btn({ label: '关闭', color: 'inherit', act: 'setLibraryOpen(false)', src: 'ResearchPage.tsx:688' })}</div>
            </div>
          </div>${VH}</div>`,
      };
    }
    const l3 = b === 'l3';
    return {
      raw: `<div class="lrow vh100" data-zone="body">
        <div class="lmain">
          ${l3 ? `<div class="lhead" data-zone="above-board">
            <span class="muted" style="font-size:.9rem">研究模式 · 第 34 手后 · 黑方胜率 54.2%</span>
            ${btn({ label: '返回编辑', variant: 'outlined', size: 'sm', icon: 'ExitToApp', act: 'handleReturnToEdit() → 回到 L1', src: 'ResearchPage.tsx:434' })}
          </div>` : ''}
          <div class="lboard"><canvas class="boardcv" data-floor="${l3 ? 200 : 400}" data-board='${esc(JSON.stringify({ stones: demoStones(l3 ? 34 : 12), coords: true, last: l3 ? [4, 11, 'B'] : null, ai: l3 ? [[15, 15, '54%', '+1.8'], [3, 3, '53%', '+0.9']] : null }))}'></canvas></div>
          ${!l3 ? `<div class="lbottom" data-zone="bottom-nav">
            ${btn({ label: '⏮', size: 'sm', color: 'inherit', act: 'board.handleMoveChange(0)', src: 'ResearchPage.tsx:608' })}
            ${btn({ label: '◀', size: 'sm', color: 'inherit', act: 'board.handleMoveChange(currentMove-1)', src: 'ResearchPage.tsx:615' })}
            <span class="mono muted" style="min-width:80px;text-align:center;margin:0 16px">12 / 12 手</span>
            ${btn({ label: '▶', size: 'sm', color: 'inherit', act: 'board.handleMoveChange(currentMove+1)', src: 'ResearchPage.tsx:630' })}
            ${btn({ label: '⏭', size: 'sm', color: 'inherit', act: 'board.handleMoveChange(moves.length)', src: 'ResearchPage.tsx:637' })}
          </div>` : ''}
        </div>
        <div class="lrail w500">
          <div class="lrail-scroll">${researchRail(l3 ? 'l3' : 'l1')}</div>
          <div style="padding:16px;border-top:1px solid var(--line)" data-zone="right-rail-actions">
            ${l3
              ? `<div class="inline" style="justify-content:center;gap:4px;margin-bottom:10px">
                   ${ibtn({ icon: 'SkipPrevious', label: '最初', act: 'handleL2MoveChange(0)', src: 'ResearchAnalysisPanel.tsx' })}
                   ${ibtn({ icon: 'NavigateBefore', label: '后退', act: 'handleL2MoveChange(n-1)', src: 'ResearchAnalysisPanel.tsx' })}
                   <button class="iconbtn" aria-label="play" data-act="自动播放" data-src="ResearchAnalysisPanel.tsx" style="background:var(--jade);color:#eef4f0">${icon('PlayArrow')}</button>
                   ${ibtn({ icon: 'NavigateNext', label: '前进', act: 'handleL2MoveChange(n+1)', src: 'ResearchAnalysisPanel.tsx' })}
                   ${ibtn({ icon: 'SkipNext', label: '最终', act: 'handleL2MoveChange(total)', src: 'ResearchAnalysisPanel.tsx' })}
                   <span class="mono muted" style="margin-left:8px;font-size:.82rem">34 / 250 手</span>
                 </div>
                 ${btn({ label: '继续分析', variant: 'contained', size: 'lg', full: true, act: '继续 KataGo 分析', src: 'ResearchAnalysisPanel.tsx' })}`
              : btn({ label: '开始研究', variant: 'contained', size: 'lg', full: true, act: 'serializeToSGF → 创建研究会话 → 进入 L2', src: 'ResearchSetupPanel.tsx' })}
          </div>
        </div>${VH}</div>`,
    };
  },
  note: `<h3>三个模式共用一个 URL</h3>
    <p><code>ResearchPage.tsx</code> 693 行里塞了三套完全不同的布局：L1 编辑（棋盘 + 底部手数条 + 右 500px 设置栏）、
    L2 全屏进度、L3 分析结果（棋盘上方多一条工具栏 + 右 500px 分析栏）。三套都用 <code>height:'100vh'</code>
    （<code>:416 / :510 / :573</code>），在 848px 的可用高度里各自超出 52px。</p>
    <p>迁移到 <code>BoardPageShell</code> 后：L3 棋盘上方那条工具栏要按 spec §2.2 清空，
    「返回编辑」是模式退出不是路由返回，得进右栏动作区；L2 那个全屏进度页没有棋盘，
    要决定它是留全屏还是变成右栏里的一个状态。</p>`,
});
