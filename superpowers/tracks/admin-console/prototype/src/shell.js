// ---------- Shell: header, sidebar with the vision-lab group, prototype panel, render loop ----------
const LAB = [['capture', '采集与数据集'], ['training', '训练与模型'], ['diagnostics', '本机部署与诊断']];
const FOOT = {
  tutorial: '修改会写入该环境的教程数据',
  cron: '此页面只读，不会运行或暂停任务。',
  performance: '只读页面，不修改配置。',
  users: '调整积分与生成兑换码会写入该环境的主库。',
  audit: '只读页面。',
  health: '只读页面，不修改配置。',
  capture: '相机、指示灯与训练帧只在 Mac 本机使用。',
  training: '训练运行在测试机；本页不会暗中连接远端。',
  diagnostics: 'viewer 只读观察，不提交棋步、不驱动指示灯。',
};
function header() {
  return `<header class="admin-top"><div class="admin-brand"><img src="__LOGO__" alt=""><span class="admin-brand-cn">智星盒</span><span class="admin-brand-en">StellaBox</span><span class="admin-brand-admin">管理后台</span></div><div class="admin-topright">${protoPanel()}<span class="admin-env">本机环境</span>${S.signedIn ? '<span>admin:fan</span><button data-act="signout">退出</button>' : ''}</div></header>`;
}
function sidebar() {
  const inLab = LAB.some(([id]) => id === S.page);
  const nav = (id, icon, text) => `<button class="admin-nav ${S.page === id ? 'active' : ''}" data-act="go" data-page="${id}" ${S.page === id ? 'aria-current="page"' : ''}>${ic(icon)}${text}</button>`;
  return `<aside class="admin-side" aria-label="管理导航"><div class="admin-sidehead">内容与服务</div>${nav('tutorial', 'book', '教程管理')}${nav('cron', 'clock', '定时任务')}${nav('performance', 'pulse', '性能监控')}${nav('users', 'users', '用户与计费')}${nav('audit', 'shield', '审计日志')}${nav('health', 'check', '配置体检')}
    <button class="admin-nav ${inLab && !S.labOpen ? 'active' : ''} ${inLab ? 'parent-active' : ''}" data-act="lab-toggle" aria-expanded="${S.labOpen}" aria-controls="lab-subnav">${ic('camera')}视觉实验室${ic('chev', 'i chev')}</button>
    ${S.labOpen ? `<div class="p-subnav" id="lab-subnav">${LAB.map(([id, text], i) => `<button data-act="go" data-page="${id}" ${S.page === id ? 'aria-current="page"' : ''}><b>${i + 1}</b>${text}</button>`).join('')}</div>` : ''}
    <div class="admin-sidefoot">当前环境：本机环境<br>${FOOT[S.page] || ''}</div></aside>`;
}
actions.go = (el) => { S.page = el.dataset.page; if (LAB.some(([id]) => id === S.page)) S.labOpen = true; render(); document.querySelector('main')?.scrollTo?.(0, 0); };
actions['lab-toggle'] = () => { S.labOpen = !S.labOpen; if (S.labOpen && !LAB.some(([id]) => id === S.page)) S.page = 'capture'; render(); };
actions.signout = () => { S.signedIn = false; render(); };
actions.signin = (el, e) => { e.preventDefault(); S.signedIn = true; render(); };

function signinPage() {
  return `<section class="admin-signin-page" aria-label="后台登录"><form class="admin-signin-card" data-submit="signin"><h1>登录管理后台</h1><p>通过 SSH 隧道访问的后台专用账号，与公开 Galaxy 账号独立。</p><label for="admin-username">后台用户名</label><input id="admin-username" value="admin:fan" autocomplete="username"><label for="admin-password">密码</label><input id="admin-password" type="password" value="prototype" autocomplete="current-password"><button type="submit">登录</button><div class="admin-signin-help">原型：点「登录」直接回到后台，不校验口令。</div></form></section>`;
}

// Prototype-only controls for states a click inside the product cannot reach (errors, stale data, theme).
const PROTO = [];
function protoPanel() {
  const groups = PROTO.filter((g) => !g.page || g.page === S.page);
  return `<div class="proto" aria-label="原型控制">${S.proto ? `<div class="box"><p>原型控制：切换页面里点不到的状态，不属于产品界面。</p>
    <div><h4>主题</h4><div class="opts"><button data-act="theme" data-v="dark" aria-pressed="${S.theme === 'dark'}">夜间 · 石墨铜</button><button data-act="theme" data-v="light" aria-pressed="${S.theme === 'light'}">白天 · 雾白蓝</button></div></div>
    ${groups.map((g) => `<div><h4>${g.title}</h4><div class="opts">${g.options.map(([v, text]) => `<button data-act="proto-set" data-g="${g.id}" data-v="${v}" aria-pressed="${g.get() === v}">${text}</button>`).join('')}</div></div>`).join('')}
  </div>` : ''}<button data-act="proto-toggle" aria-expanded="${S.proto}">${ic('layers')}原型控制</button></div>`;
}
actions['proto-toggle'] = () => { S.proto = !S.proto; render(); };
actions.theme = (el) => { S.theme = el.dataset.v; render(); };
actions['proto-set'] = (el) => { const g = PROTO.find((x) => x.id === el.dataset.g); g.set(el.dataset.v); render(); };

function render() {
  const root = document.getElementById('app');
  const focusId = document.activeElement?.id;
  const main = document.querySelector('main');
  const scroll = main ? main.scrollTop : 0;
  const openDetails = [...root.querySelectorAll('details[open][data-key]')].map((d) => d.dataset.key);
  const pageCls = S.page === 'tutorial' ? 'admin-app-tutorial' : 'admin-app-cron';
  const body = S.signedIn ? `<div class="admin-wrap">${sidebar()}${pages[S.page].render()}</div>` : signinPage();
  root.innerHTML = `<div class="admin-app ${pageCls}" data-theme="${S.theme}" style="position:relative">${header()}${body}${modalHTML()}</div>`;
  const nextMain = document.querySelector('main');
  if (nextMain && scroll) nextMain.scrollTop = scroll;
  openDetails.forEach((k) => root.querySelector(`details[data-key="${k}"]`)?.setAttribute('open', ''));
  if (focusId) document.getElementById(focusId)?.focus?.({ preventScroll: true });
  pages[S.page]?.after?.();
}

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-act]');
  if (!el || el.disabled) return;
  const fn = actions[el.dataset.act];
  if (fn) fn(el, e);
});
document.addEventListener('change', (e) => { const el = e.target.closest('[data-change]'); if (el) actions[el.dataset.change]?.(el, e); });
document.addEventListener('input', (e) => { const el = e.target.closest('[data-input]'); if (el) actions[el.dataset.input]?.(el, e); });
document.addEventListener('submit', (e) => { const el = e.target.closest('[data-submit]'); if (el) { e.preventDefault(); actions[el.dataset.submit]?.(el, e); } });
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && S.modal) { S.modal = null; render(); return; }
  if (e.target.closest('input,select,textarea')) return;
  pages[S.page]?.key?.(e);
});
