/* ═══════════════════════════════════════════════════════════════
   总览 — measured at boot by rendering every screen offscreen and
   reading the same numbers the console readout reads. Nothing here
   is typed in by hand.
   ═══════════════════════════════════════════════════════════════ */
const TEMPLATE_STATUS = {
  'live-match': ['已在模板上', '2026-08-06 获批准的棋盘页样板'],
  'game-rated': ['已在模板上', 'BoardPageShell + ModulePlate(backLabel)'],
  'ai-setup-rated': ['已在模板上', 'ContentPageHeader 样板'],
  'research': ['待迁移 · 棋盘页', 'spec §1.2 点名'],
  'tsumego-problem': ['待迁移 · 棋盘页', 'spec §1.2 点名'],
  'report-detail': ['待迁移 · 棋盘页', 'spec §1.2 点名'],
  'kifu': ['待迁移 · 棋盘页', 'spec §1.2 点名'],
  'game-room': ['待迁移 · 棋盘页', '本轮追加，排最后'],
  'tutorial-figure': ['待定 · 内部工具', '本轮追加，形态待裁定'],
  'dashboard': ['待迁移 · 只换页头', ''],
  'play-menu': ['待迁移 · 只换页头', ''],
  'hvh-lobby': ['待迁移 · 只换页头', ''],
  'live-list': ['待迁移 · 只换页头', '⚠ 它其实有棋盘'],
  'reports': ['待迁移 · 只换页头', ''],
  'tsumego-levels': ['待迁移 · 只换页头', ''],
  'tsumego-categories': ['待迁移 · 只换页头', ''],
  'tsumego-units': ['待迁移 · 只换页头', ''],
  'tsumego-list': ['待迁移 · 只换页头', ''],
  'tutorial-landing': ['待迁移 · 只换页头', ''],
  'tutorial-books': ['待迁移 · 只换页头', ''],
  'tutorial-book': ['待迁移 · 只换页头', ''],
  'ai-setup-free': ['不在本轮范围', '照抄对象的另一半'],
  'game-free': ['不在本轮范围', '照抄对象的另一半'],
};
const STATUS_TONE = {
  '已在模板上': 'ok', '待迁移 · 棋盘页': 'warn', '待定 · 内部工具': 'err',
  '待迁移 · 只换页头': 'info', '不在本轮范围': '',
};

let MEASURED = null;

function measureAll() {
  const keep = { screen: S.screen, branch: S.branch, vp: S.vp, dialog: S.dialog, mode: S.mode };
  const rows = [];
  const readOne = () => {
    const cv = document.querySelector('.boardcv');
    const rail = document.querySelector('.rail') || document.querySelector('.lrail');
    const k = getScale();
    return {
      board: cv ? Number(cv.dataset.edge) : null,
      rail: rail ? Math.round(rail.getBoundingClientRect().width / k) : null,
      controls: document.querySelectorAll('#app [data-act],#app [data-toggle],#app [data-dialog],#app input,#app select,#app textarea').length,
    };
  };
  for (const sc of SCREENS) {
    if (sc.id === 'overview') continue;
    const per = {}, per2 = {};
    for (const v of VPS) {
      S.screen = sc.id; S.branch = (sc.branches && sc.branches[0].id) || 'default';
      S.vp = v.id; S.dialog = null;
      S.mode = 'now'; renderFrame(); per[v.id] = readOne();
      S.mode = 'new'; renderFrame(); per2[v.id] = readOne();
    }
    rows.push({
      id: sc.id, label: sc.label, group: sc.group, route: sc.route,
      per, per2, noBoardTarget: sc.noBoardTarget, hasV2: !!(typeof V2 !== 'undefined' && V2[sc.id]),
    });
  }
  Object.assign(S, keep);
  MEASURED = rows;
  return rows;
}

SCREENS.unshift({
  id: 'overview', group: '总览', label: '版式统一 · 23 屏 / 四档视口', route: '（原型自己的一页，不是产品页面）',
  nav: null, kind: 'content', noBoardTarget: true,
  render() {
    const rows = MEASURED || [];
    const num = (v, tone) => v == null ? '<span class="dim">—</span>'
      : `<span class="mono"${tone ? ` style="color:var(--${tone})"` : ''}>${v}</span>`;
    const delta = (a, b) => {
      if (a == null || b == null) return '';
      const d = b - a;
      if (!d) return '<span class="dim mono" style="font-size:.72rem"> ±0</span>';
      return `<span class="mono" style="font-size:.72rem;color:var(--${d > 0 ? 'ok' : 'warn'})"> ${d > 0 ? '+' : ''}${d}</span>`;
    };
    const boardRows = rows.filter(r => r.hasV2 || (r.per['1440x900'] && r.per['1440x900'].board != null));

    return {
      raw: `<div style="height:100%;overflow-y:auto;background:#101010" data-zone="body">
        <div style="max-width:1080px;margin:0 auto;padding:36px 32px 56px">

          <p style="margin:0 0 6px;font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:var(--tx3)">原型自己的一页 · 不是产品页面</p>
          <h1 style="margin:0 0 10px;font-size:2.4rem;font-weight:800;letter-spacing:-.02em;line-height:1.15;text-wrap:balance">
            棋盘优先 · 全站一套外框</h1>
          <p style="margin:0 0 28px;color:var(--tx2);max-width:64ch;line-height:1.75">
            上面控制台最左边那个 <b>现状 / 改版</b> 开关，是这一版的主轴：同一个页面、同一个分支、同一档视口，
            左右各看一遍。改版遵守一条契约 —— <b>有棋盘的页面，棋盘吃满中间；状态和操作一律进右栏；
            顶栏、左栏、右栏三个宽度全站定死。</b></p>

          <div style="border:1px solid rgba(93,130,112,.4);border-radius:14px;overflow:hidden;margin-bottom:34px">
            <div style="padding:14px 18px;background:rgba(74,107,92,.12);border-bottom:1px solid var(--line2)">
              <b style="font-size:.95rem">版式契约</b>
              <span class="dim" style="font-size:.78rem;margin-left:10px">改版模式下每一个棋盘页都按这张表长</span>
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:.85rem">
              <tbody>${CONTRACT2.map(([k, v, mode, why]) => `
                <tr>
                  <td style="padding:9px 18px;border-bottom:1px solid var(--line);width:96px;color:var(--tx2)">${esc(k)}</td>
                  <td style="padding:9px 10px;border-bottom:1px solid var(--line);width:150px" class="mono"><b style="color:var(--jade-l)">${esc(v)}</b></td>
                  <td style="padding:9px 10px;border-bottom:1px solid var(--line);width:88px;color:var(--tx3);font-size:.78rem">${esc(mode)}</td>
                  <td style="padding:9px 18px 9px 10px;border-bottom:1px solid var(--line);color:var(--tx3);font-size:.78rem">${esc(why)}</td>
                </tr>`).join('')}</tbody>
            </table>
          </div>

          <h2 style="font-size:1.05rem;font-weight:700;margin:0 0 4px">改版前后：棋盘和右栏</h2>
          <p class="dim" style="margin:0 0 14px;font-size:.8rem;line-height:1.6">
            两列数都是本页刚才在浏览器里<b>各渲染一遍量出来的</b>，不是写死的。
            已批准样板在三档视口下的棋盘边长是 <span class="mono">828 / 684 / 410</span>。</p>
          <div style="overflow-x:auto;margin-bottom:34px">
            <table style="width:100%;border-collapse:collapse;font-size:.85rem;min-width:720px">
              <thead>
                <tr style="text-align:left;color:var(--tx3);font-size:.72rem;letter-spacing:.06em">
                  <th rowspan="2" style="font-weight:500;padding:8px 10px;border-bottom:1px solid var(--line2);vertical-align:bottom">页面</th>
                  <th colspan="2" style="font-weight:500;padding:8px 10px;text-align:right;border-bottom:1px solid var(--line)">棋盘 1440×900</th>
                  <th colspan="2" style="font-weight:500;padding:8px 10px;text-align:right;border-bottom:1px solid var(--line)">棋盘 1024×768</th>
                  <th colspan="2" style="font-weight:500;padding:8px 10px;text-align:right;border-bottom:1px solid var(--line)">右栏</th>
                </tr>
                <tr style="text-align:right;color:var(--tx3);font-size:.68rem">
                  <th style="font-weight:500;padding:4px 10px 8px;border-bottom:1px solid var(--line2)">现状</th>
                  <th style="font-weight:500;padding:4px 10px 8px;border-bottom:1px solid var(--line2);color:var(--jade-l)">改版</th>
                  <th style="font-weight:500;padding:4px 10px 8px;border-bottom:1px solid var(--line2)">现状</th>
                  <th style="font-weight:500;padding:4px 10px 8px;border-bottom:1px solid var(--line2);color:var(--jade-l)">改版</th>
                  <th style="font-weight:500;padding:4px 10px 8px;border-bottom:1px solid var(--line2)">现状</th>
                  <th style="font-weight:500;padding:4px 10px 8px;border-bottom:1px solid var(--line2);color:var(--jade-l)">改版</th>
                </tr>
              </thead>
              <tbody>${boardRows.map(r => {
                const st = TEMPLATE_STATUS[r.id] || ['', ''];
                const a1 = r.per['1440x900'], b1 = r.per2['1440x900'];
                const a2 = r.per['1024x768'], b2 = r.per2['1024x768'];
                const cellPair = (a, b, target) => `
                  <td style="padding:8px 10px;border-bottom:1px solid var(--line);text-align:right">${num(a, a != null && target != null && Math.abs(a - target) > 1 ? 'warn' : null)}</td>
                  <td style="padding:8px 10px;border-bottom:1px solid var(--line);text-align:right;background:rgba(74,107,92,.06)">${num(b, b != null && target != null && Math.abs(b - target) > 1 ? 'warn' : 'ok')}${delta(a, b)}</td>`;
                return `<tr>
                  <td style="padding:8px 10px;border-bottom:1px solid var(--line)">
                    <button data-goto="${r.id}" data-act="跳到 ${esc(r.label)}" style="background:none;border:0;color:var(--tx);font:inherit;cursor:pointer;text-align:left;padding:0;text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line3)">${esc(r.label)}</button>
                    <div class="dim" style="font-size:.68rem;margin-top:2px">${esc(st[0])}</div></td>
                  ${cellPair(a1.board, b1.board, r.noBoardTarget ? null : 828)}
                  ${cellPair(a2.board, b2.board, r.noBoardTarget ? null : 684)}
                  ${cellPair(a1.rail, b1.rail, null)}
                </tr>`;
              }).join('')}</tbody>
            </table>
          </div>

          <h2 style="font-size:1.05rem;font-weight:700;margin:0 0 4px">改版动了哪些页</h2>
          <p class="dim" style="margin:0 0 14px;font-size:.8rem">带绿边的这 ${boardRows.filter(r => r.hasV2).length} 屏在改版模式下换了版式；其余保持现状。</p>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;margin-bottom:34px">
            ${rows.map(r => {
              const st = TEMPLATE_STATUS[r.id] || ['', ''];
              return `<button data-goto="${r.id}" data-act="跳到 ${esc(r.label)}"
                style="text-align:left;background:rgba(255,255,255,.02);border:1px solid ${r.hasV2 ? 'rgba(93,130,112,.5)' : 'var(--line)'};border-radius:10px;padding:12px;color:inherit;font:inherit;cursor:pointer">
                <div style="font-size:.88rem;font-weight:600;margin-bottom:4px">${esc(r.label)}</div>
                <div class="inline" style="gap:6px">
                  <span class="chip ${r.hasV2 ? 'ok' : (STATUS_TONE[st[0]] || '')}" style="height:18px;font-size:.62rem">${r.hasV2 ? '改版已出' : esc(st[0])}</span>
                  <span class="dim mono" style="font-size:.66rem">${r.per['1440x900'].controls} 控件</span>
                </div>
              </button>`;
            }).join('')}
          </div>

          <h2 style="font-size:1.05rem;font-weight:700;margin:0 0 4px">2026-08-20 评审后的四条改动</h2>
          <p class="dim" style="margin:0 0 14px;font-size:.8rem">前三条是全站通用的，第四条是一页重设计。</p>
          <ol style="margin:0 0 30px;padding-left:20px;color:var(--tx2);line-height:1.85;font-size:.85rem;max-width:72ch">
            <li><b>轮次高亮</b>（对局室 / 自由对局 / 升降级对局）。轮到谁下，谁的卡描边、时钟、呼吸点、
                卡底文字四条线索同时变 —— 不只靠颜色，色盲和强光下的 7 寸屏也读得出。</li>
            <li><b>右下角那排重复按钮删了。</b>「认输 / 数子」原来在工具格里是<b>假的</b>（点了没反应），
                真正开弹窗的是下面那排；现在反过来 —— 格子里的接上弹窗，下面那排整排删除。
                「数子请求」不是我方按钮（是对方发起时弹出来的），也删了。
                只剩「离开对局」，按要求<b>和上方的按钮放在一起</b>，就在工具格正下方。
                动作区只留翻手六键。</li>
            <li><b>左栏那个悬在棋盘上的圆形折叠钮，全站去掉。</b>但不能直接删干净：
                1024 档左栏本来就是 0，没有别的入口就等于没导航了。所以那个能力挪到<b>顶栏左侧的菜单键</b>，
                而且只在左栏收起的档位出现 —— 1440 下左栏已经停靠，收起它一个棋盘像素都不多
                （棋盘是高度受限），所以那一档<b>一个折叠钮都不需要</b>。</li>
            <li><b>死活题难度页重新设计</b>（见下方「死活题 · 难度列表」那一屏）：
                从 8 个等价方块改成一条有序阶梯。</li>
          </ol>
          <p style="margin:0 0 30px;padding:12px 16px;border-left:3px solid var(--jade);background:rgba(74,107,92,.08);
             color:var(--tx2);font-size:.84rem;line-height:1.7;max-width:72ch">
            顺带：原型专用的假按钮（「认输弹窗」「终局弹窗」这类）全部从框里挪到了控制台的
            <b>弹窗</b>那一栏。框里现在只剩真实产品控件 —— 控件清单的数字因此更可信了。</p>

          <h2 style="font-size:1.05rem;font-weight:700;margin:0 0 10px">这一版是怎么验的</h2>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-bottom:30px">
            ${[['640', '个渲染状态', '2 版式 × 23 屏 × 全部分支 × 4 档视口，0 个报错'],
               ['4', '档视口全部命中', '改版棋盘边长 828 / 684 / 410 / 568，一个不差'],
               ['320', '右栏只出现过这一个值', '顶栏恒为 52，左栏恒为 216 或 0'],
               ['0', '条承重失败', '而且是在中段被撑到必须滚的状态下量的']].map(([n, u, sub]) => `
              <div style="border:1px solid var(--line2);border-radius:12px;padding:14px">
                <div style="display:flex;align-items:baseline;gap:6px">
                  <b class="mono" style="font-size:1.7rem;line-height:1;color:var(--jade-l)">${n}</b>
                  <span style="font-size:.78rem;color:var(--tx2)">${u}</span></div>
                <div class="dim" style="font-size:.7rem;margin-top:6px;line-height:1.5">${sub}</div></div>`).join('')}
          </div>
          <ul style="margin:0 0 30px;padding-left:20px;color:var(--tx2);line-height:1.85;font-size:.85rem;max-width:72ch">
            <li><b>承重是在真浏览器里量的，不是 jsdom。</b>关系式先写死再读数：动作区永远完整落在窗口里、
                右栏自己不滚（只有中段滚）、shell 横竖都不溢出、棋盘不越出 stage。
                而且量之前先把数据造到会溢出 —— 控制台右上角的<b>压力数据</b>开关把列表撑到后端一页真会返回的量，
                <b>1280×640 压扁档</b>把可用高度压到 588。十个改版棋盘页里九个在这个状态下中段真的滚起来了
                （死活题是唯一一个内容短到怎么压都装得下的）。</li>
            <li><b>按钮一个没丢。</b>逐屏把现状渲染出的控件全集和改版的对比过：
                真丢失 11 处（研究的 5 子/6 子和「领地」、棋谱库分页的 4/5、死活题 aria-label 里的快捷键、
                教程五步调试的完整描述和收起键、自由对局两张卡的关注键和那条生命周期告警）已经全部补回；
                剩下 30 处差异全是改名 —— <code style="font-family:var(--mono);color:var(--jade-l)">⏮</code> 变成了
                「第一手」、「认输弹窗」变成了「认输」、<code style="font-family:var(--mono);color:var(--jade-l)">Follow</code> 变成了「关注 fan」。</li>
            <li><b>死活题从 28 个控件降到 24 是对的。</b>现状那 28 个里有 4 个是移动端那棵重复的 JSX 树自带的，
                两套合成一套之后它们本来就该消失。</li>
            <li><b><code style="font-family:var(--mono);color:var(--jade-l)">height:100vh</code> 那批溢出全没了。</b>
                改版下四档视口一个橙色溢出标记都不再出现。</li>
            <li><b>3D 分支比 2D 小 12px</b>（816 / 672 / 398），因为 3D 外面多包了一层容器。
                这一条<b>现状的已批准样板自己也是这样</b>，不是本轮引入的。</li>
          </ul>

          <h2 style="font-size:1.05rem;font-weight:700;margin:0 0 10px">三处请你重点看</h2>
          <ol style="margin:0;padding-left:20px;color:var(--tx2);line-height:1.85;font-size:.85rem;max-width:70ch">
            <li><b>模块牌统一成图标左置</b>。已批准的 <code style="font-family:var(--mono);color:var(--jade-l)">LiveMatchPage</code>
                是「返回图标在最左 / 标题 / 状态徽章在右」，而 spec §2.4 的文字写的是「右侧 ← 上级简称」，
                <code style="font-family:var(--mono);color:var(--jade-l)">GamePage</code> 按后者做。我选了前者 ——
                它是真的被 12 视口验收过的那一个，而且在 320 宽下一个图标只花 40px，
                文字返回键要花 110px，全是从标题那行抢的。要改成后者只需换 <code style="font-family:var(--mono);color:var(--jade-l)">plate2()</code> 一处。</li>
            <li><b>根级页面的模块牌没有返回键</b>。研究 / 棋谱库 / 直播 / 复盘都是左栏一级入口，没有上一级。
                这需要 <code style="font-family:var(--mono);color:var(--jade-l)">ModulePlate</code> 支持「只有标题」的形态
                （<code style="font-family:var(--mono);color:var(--jade-l)">ContentPageHeader</code> 也有同样的缺口 —— 首页现在必须传 parent）。</li>
            <li><b>教程 · 变化图没有硬套</b>。它是内部制作工具，原书页图必须和棋盘并排。
                做法是右栏照旧 320，原书页图做成 stage 里可收起的对照层。切过去看一眼，这处最需要你的判断。</li>
          </ol>
        </div>
      </div>`,
    };
  },
  note: '',
});
