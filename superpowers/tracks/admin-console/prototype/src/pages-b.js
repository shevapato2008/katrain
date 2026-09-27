// ---------- 用户与计费 / 审计日志（示意数据，全部标注为原型） ----------
P.users = '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7m2.5 8.5a6.5 6.5 0 0 0-3-5.5"/>';
P.coin = '<circle cx="12" cy="12" r="9"/><path d="M9 9.5c0-1.4 1.3-2 3-2s3 .7 3 2-1.3 1.8-3 2.3-3 1-3 2.4 1.3 2.3 3 2.3 3-.8 3-2.1M12 5.5v2m0 9v2"/>';
P.ticket = '<path d="M3 8a2 2 0 0 0 0 4v0a2 2 0 0 1 0 4v2h18v-2a2 2 0 0 1 0-4 2 2 0 0 0 0-4V6H3z"/><path d="M14 6v12" stroke-dasharray="2 2"/>';
P.shield = '<path d="M12 3 4 6v6c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V6z"/><path d="m9 12 2 2 4-4"/>';

const UB = {
  tab: 'users', q: '', selected: 3, detailTab: 'ledger', page: 1,
  users: [
    { id: 1, username: 'fan', rank: '3d', credits: 1260, created: '2026-03-02', admin: true, uuid: '7c1e0a4bd3f94f6e8a4f0f2e61b7d0a1' },
    { id: 2, username: 'liuyang', rank: '5k', credits: 40, created: '2026-05-11', admin: false, uuid: '0b9d5c7e41a2483f9b4c1e7a90d3f266' },
    { id: 3, username: 'chenjing', rank: '1d', credits: 330, created: '2026-06-20', admin: false, uuid: 'e41b7d09c2a54f5a8d1e3b6c7f0a9e12' },
    { id: 4, username: 'wangpei', rank: '12k', credits: 0, created: '2026-07-04', admin: false, uuid: '5a6c2e1f9b0d4c3a8e7f6d5c4b3a2918' },
    { id: 5, username: 'zhaoxin', rank: '2k', credits: 980, created: '2026-08-15', admin: false, uuid: '9f2ca1e7b3d54a6c8e0f1d2c3b4a5968' },
    { id: 6, username: 'sunmo', rank: '8k', credits: 120, created: '2026-09-01', admin: false, uuid: 'c3d2e1f0a9b84c7d6e5f4a3b2c1d0e9f' },
  ],
  ledger: [
    ['2026-09-26 21:14', 'report', -30, 'reserved', 330, 'report:4411'],
    ['2026-09-25 10:02', 'analysis_territory', -10, 'committed', 360, 'territory:9812'],
    ['2026-09-24 18:40', 'admin_adjust', 190, 'committed', 370, 'admin_adjust:6f1c…'],
    ['2026-09-20 09:15', 'redeem', 100, 'committed', 180, 'redeem:4f2a…e81b'],
    ['2026-09-18 16:33', 'hints', -10, 'refunded', null, 'hints:7710'],
    ['2026-09-01 08:00', 'signup_grant', 80, 'committed', 80, 'signup:3'],
  ],
  batches: [
    { at: '2026-09-24 18:02', count: 20, credits: 100, expires: '2026-12-23', used: 7, by: 'admin:fan' },
    { at: '2026-09-10 11:40', count: 5, credits: 1200, expires: '2026-12-09', used: 5, by: 'admin:fan' },
  ],
  codes: [
    ['4f2a…e81b', 100, '2026-12-23', 'chenjing', '2026-09-20 09:15'],
    ['b7c1…09d3', 100, '2026-12-23', 'liuyang', '2026-09-22 20:41'],
    ['e03f…71aa', 100, '2026-12-23', null, null],
    ['91d8…c2f0', 100, '2026-12-23', null, null],
    ['2a6e…5b17', 1200, '2026-12-09', 'zhaoxin', '2026-09-12 13:05'],
  ],
  gen: { count: 20, credits: 100, days: 90 },
  adjust: null,
};
const REASON = { report: '复盘预扣', analysis_territory: '形势判断', admin_adjust: '后台调整', redeem: '兑换码', hints: '提示', signup_grant: '注册赠送' };
const TXS = { committed: ['ok', '已入账'], reserved: ['warn', '预扣中'], refunded: ['', '已退回'] };

PROTO.push({ id: 'env', page: 'users', title: '环境', options: [['test', '测试环境'], ['prod', '生产环境']], get: () => S.env || 'test', set: (v) => { S.env = v; } });
pages.users = {
  render() {
    const env = S.env || 'test';
    const tabs = [['users', 'users', '用户'], ['codes', 'ticket', '兑换码']].map(([id, icon, text]) => `<button class="tab" role="tab" aria-selected="${UB.tab === id}" data-act="ub-tab" data-v="${id}">${ic(icon)}${text}</button>`).join('');
    return `<main class="lab-page"><div class="lab-heading"><div><h1>用户与计费</h1><p>查看账户与积分账本，调整余额、生成兑换码；每次写入都记审计</p></div><span class="lab-status ${env === 'prod' ? 'bad' : ''}">${ic(env === 'prod' ? 'warn' : 'info')}${env === 'prod' ? '生产环境 · 写入即真实生效' : '测试环境 · 写入会改测试库'}</span></div>
      <div class="lab-content"><div class="panel"><div class="tabs" role="tablist">${tabs}</div></div>${UB.tab === 'users' ? usersTab() : codesTab()}</div></main>`;
  },
  key(e) { if (UB.tab === 'users' && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) { const i = UB.users.findIndex((u) => u.id === UB.selected) + (e.key === 'ArrowDown' ? 1 : -1); if (UB.users[i]) { UB.selected = UB.users[i].id; render(); } } },
};
function usersTab() {
  const list = UB.users.filter((u) => !UB.q || u.username.startsWith(UB.q) || String(u.id) === UB.q || u.uuid === UB.q);
  const u = UB.users.find((x) => x.id === UB.selected) || list[0];
  const rows = list.map((x) => `<button class="ub-row ${x.id === u?.id ? 'on' : ''}" data-act="ub-pick" data-id="${x.id}"><span class="mono">${x.id}</span><span class="ub-name">${esc(x.username)}${x.admin ? ' <span class="chip">管理员</span>' : ''}</span><span>${x.rank}</span><span class="num">${x.credits}</span><span class="muted">${x.created}</span></button>`).join('');
  return `<div class="ub-grid"><section class="panel ub-list"><div class="panel-head"><h2>用户</h2><small>共 1,284 人 · 第 ${UB.page} / 65 页</small></div>
      <div class="ub-search"><label class="field ub-q">${ic('search')}<input placeholder="用户名前缀、id 或 uuid" value="${esc(UB.q)}" data-input="ub-q" aria-label="搜索用户"></label></div>
      <div class="ub-thead"><span>id</span><span>用户名</span><span>段位</span><span class="num">余额</span><span>注册</span></div>
      <div class="ub-rows">${rows || '<div class="empty-view"><small>没有匹配的用户</small></div>'}</div>
      <div class="ub-pager"><button class="btn small" disabled>上一页</button><span class="note">每页 20 人</span><button class="btn small" data-act="ub-page">下一页</button></div></section>
    ${u ? userDetail(u) : '<section class="panel"><div class="empty-view">选择一位用户</div></section>'}</div>`;
}
function userDetail(u) {
  const dt = [['ledger', '账本流水'], ['quota', '会员额度'], ['redeemed', '兑换记录']].map(([id, t]) => `<button class="tab" role="tab" aria-selected="${UB.detailTab === id}" data-act="ub-dtab" data-v="${id}">${t}</button>`).join('');
  const ledger = `<div class="ub-ledger"><div class="ub-lhead"><span>时间</span><span>事由</span><span class="num">变动</span><span>状态</span><span class="num">余额</span></div>${UB.ledger.map(([at, r, d, st, bal, ref]) => `<div class="ub-lrow ${st === 'reserved' ? 'hold' : ''}"><span class="muted">${at}</span><span>${REASON[r] || r}<small title="${ref}">${ref}</small></span><span class="num ${st === 'refunded' ? 'void' : d > 0 ? 'plus' : 'minus'}">${d > 0 ? '+' : ''}${d}</span><span><span class="chip ${TXS[st][0]}">${TXS[st][1]}</span></span><span class="num">${bal ?? '—'}</span></div>`).join('')}</div><div class="ub-pager"><span class="note">最近 50 条 · 预扣中的行高亮 · 已退回的预扣不计入余额</span><button class="btn small">更早</button></div>`;
  const quota = `<div class="ub-quota">${[['复盘报告', '本周', 1, 3], ['形势判断', '今天', 4, 20], ['提示', '今天', 0, 10]].map(([k, p, used, all]) => `<div><strong>${k}</strong><span class="note">${p}</span><div class="ub-bar"><i style="width:${used / all * 100}%"></i></div><span class="num">${used} / ${all}</span></div>`).join('')}<p class="note">只读 · 额度按周期自动换桶，不在后台编辑</p></div>`;
  const redeemed = `<div class="ub-ledger"><div class="ub-lhead two"><span>兑换码</span><span class="num">面额</span><span>兑换时间</span></div><div class="ub-lrow two"><span class="mono">4f2a…e81b</span><span class="num">100</span><span class="muted">2026-09-20 09:15</span></div></div>`;
  return `<section class="panel ub-detail"><div class="ub-dhead"><div><h2>${esc(u.username)} ${u.admin ? '<span class="chip">管理员</span>' : ''}</h2><p class="mono note">id ${u.id} · uuid ${u.uuid}</p></div><div class="ub-balance"><span class="note">可用余额</span><strong class="num">${u.credits}</strong><span class="note">另预扣 30</span></div></div>
    <dl class="ub-facts"><div><dt>段位</dt><dd>${u.rank}</dd></div><div><dt>注册时间</dt><dd>${u.created}</dd></div><div><dt>预扣中</dt><dd>30 积分 · 1 笔</dd></div><div><dt>累计后台调整</dt><dd>+200</dd></div></dl>
    <div class="ub-actions"><button class="btn primary" data-act="ub-adjust">${ic('coin')}调整积分</button><span class="note">加或扣都追加一条账本行，不改历史</span></div>
    <div class="tabs" role="tablist">${dt}</div>${UB.detailTab === 'ledger' ? ledger : UB.detailTab === 'quota' ? quota : redeemed}</section>`;
}
function codesTab() {
  const g = UB.gen;
  return `<div class="ub-codes"><section class="panel"><div class="panel-head"><h2>生成一批兑换码</h2><small>码值只在生成后显示一次</small></div>
      <div class="ub-genform"><label class="field">数量（1–200）<input type="number" min="1" max="200" value="${g.count}" data-input="ub-gen" data-k="count"></label><label class="field">每个面额（1–12000 积分）<input type="number" min="1" max="12000" value="${g.credits}" data-input="ub-gen" data-k="credits"></label><label class="field">有效期（天，≤365）<input type="number" min="1" max="365" value="${g.days}" data-input="ub-gen" data-k="days"></label><label class="field ub-wide">用途（写进审计，至少 5 个字）<input placeholder="例如：九月线下活动奖品" data-input="ub-gen" data-k="note"></label>
      <div class="ub-gensum"><span class="note">合计 <strong>${g.count * g.credits}</strong> 积分 · 到期 2026-12-26</span><button class="btn primary" data-act="ub-gen">${ic('ticket')}生成</button></div></div></section>
    <section class="panel"><div class="panel-head"><h2>已生成的兑换码</h2><small>码值已打码 · 不提供再次查看</small></div>
      <div class="ub-batches">${UB.batches.map((b) => `<div><strong>${b.at}</strong><span>${b.count} 个 × ${b.credits} 积分</span><span class="note">到期 ${b.expires}</span><span class="chip ${b.used === b.count ? '' : 'ok'}">已用 ${b.used} / ${b.count}</span><span class="note">${b.by}</span></div>`).join('')}</div>
      <div class="ub-ledger"><div class="ub-lhead codes"><span>兑换码</span><span class="num">面额</span><span>到期</span><span>状态</span><span>使用者</span><span>使用时间</span></div>${UB.codes.map(([c, cr, exp, by, at]) => `<div class="ub-lrow codes"><span class="mono">${c}</span><span class="num">${cr}</span><span class="muted">${exp}</span><span><span class="chip ${by ? '' : 'ok'}">${by ? '已用' : '未用'}</span></span><span>${by || '—'}</span><span class="muted">${at || '—'}</span></div>`).join('')}</div></section></div>`;
}
actions['ub-tab'] = (el) => { UB.tab = el.dataset.v; render(); };
actions['ub-dtab'] = (el) => { UB.detailTab = el.dataset.v; render(); };
actions['ub-pick'] = (el) => { UB.selected = +el.dataset.id; render(); };
actions['ub-page'] = () => { UB.page = Math.min(65, UB.page + 1); render(); };
actions['ub-q'] = (el) => { UB.q = el.value.trim(); render(); };
actions['ub-gen'] = (el) => { if (el.dataset.k) { UB.gen[el.dataset.k] = el.dataset.k === 'note' ? el.value : +el.value; return; } const codes = Array.from({ length: UB.gen.count }, (_, i) => (i * 2654435761 >>> 0).toString(16).padStart(8, '0') + '9e81b0c2d4f6a8e1' + (i * 40503 >>> 0).toString(16).padStart(8, '0'));
  confirmModal({ title: `已生成 ${UB.gen.count} 个兑换码`, wide: true, body: `<p class="note">码值只显示这一次。关闭后列表里只剩打码后的样子。</p><pre class="ub-codelist">${codes.join('\n')}</pre><div class="ub-actions flush"><button class="btn primary">${ic('file')}下载 CSV</button><button class="btn">复制全部</button></div>`, check: '我已保存这批码值。' }); };
actions['ub-adjust'] = () => { UB.adjust = { amount: 200, reason: '' }; const u = UB.users.find((x) => x.id === UB.selected);
  confirmModal({ title: `调整 ${u.username} 的积分${(S.env || 'test') === 'prod' ? ' <span class="chip bad">生产环境</span>' : ''}`, body: `<div class="ub-adjform"><label class="field">变动（正数加、负数扣，绝对值 ≤ 12000）<input type="number" value="-50"></label><label class="field">原因（写进审计，至少 5 个字）<input value="误发补偿退回"></label><div class="ub-confirmbox"><p class="note">再输入一次用户名和变动，与上面一致才能提交：</p><label class="field">用户名<input placeholder="再输入目标用户名"></label><label class="field">变动<input placeholder="再输入变动"></label></div><p class="note">余额 ${u.credits} → ${u.credits - 50}。扣减不会让余额低于 0。</p><p class="ub-err">${ic('warn')}两次输入不一致：用户名与变动都要和上面相同</p></div>`, accept: '确认调整', check: '我已核对用户与金额。', onAccept: () => { u.credits -= 50; } }); };

// ---------- 审计日志 ----------
const AU = { action: 'all' };
const AUDIT = [
  ['2026-09-27 09:12:04', 'admin:fan', 'credit_adjust', 'user 3 · chenjing', true, '-50 · 误发补偿退回 · 余额 330→280'],
  ['2026-09-27 09:05:47', 'admin:fan', 'redeem_codes_generate', '批次 20 × 100', true, '九月线下活动奖品 · 到期 2026-12-26'],
  ['2026-09-27 09:01:30', 'admin:fan', 'login', '—', true, ''],
  ['2026-09-26 22:40:11', 'admin:fan', 'tutorial_figure_update', 'tutorial_figure 1182', true, ''],
  ['2026-09-26 22:38:02', 'admin:fan', 'login_failed', '—', false, ''],
  ['2026-09-24 18:40:19', 'admin:fan', 'credit_adjust', 'user 3 · chenjing', true, '+200 · 活动奖励 · 余额 170→370'],
];
const ACTION_LABEL = { credit_adjust: '积分调整', redeem_codes_generate: '生成兑换码', login: '登录', login_failed: '登录失败', logout: '退出', tutorial_figure_update: '教程修改' };
pages.audit = {
  render() {
    const rows = AUDIT.filter((r) => AU.action === 'all' || r[2] === AU.action);
    return `<main class="lab-page"><div class="lab-heading"><div><h1>审计日志</h1><p>后台账号的登录与每一次写入，只读</p></div><span class="lab-status">${ic('shield')}与业务写入同一事务提交</span></div>
      <div class="lab-content"><section class="panel au-filter"><label class="field">动作<select data-change="au-action"><option value="all">全部</option>${Object.entries(ACTION_LABEL).map(([k, v]) => `<option value="${k}" ${AU.action === k ? 'selected' : ''}>${v}</option>`).join('')}</select></label><label class="field">起<input type="date" value="2026-09-20"></label><label class="field">止<input type="date" value="2026-09-27"></label><label class="field">目标用户 id<input placeholder="例如 3"></label><button class="btn">${ic('search')}筛选</button></section>
        <section class="panel"><div class="panel-head"><h2>记录</h2><small>${rows.length} 条 · 按时间倒序</small></div>
        <div class="ub-ledger"><div class="ub-lhead audit"><span>时间</span><span>操作者</span><span>动作</span><span>目标</span><span>结果</span><span>详情</span></div>${rows.map(([at, who, a, t, ok, d]) => `<div class="ub-lrow audit"><span class="muted mono">${at}</span><span>${who}</span><span>${ACTION_LABEL[a]}<small>${a}</small></span><span>${t}</span><span><span class="chip ${ok ? 'ok' : 'bad'}">${ok ? '成功' : '失败'}</span></span><span class="muted">${d || '—'}</span></div>`).join('')}</div>
        <div class="ub-pager"><button class="btn small" disabled>上一页</button><span class="note">每页 50 条</span><button class="btn small" disabled>下一页</button></div></section></div></main>`;
  },
};
actions['au-action'] = (el) => { AU.action = el.value; render(); };

// ---------- 配置体检 ----------
const CH = { scenario: 'mixed' };
PROTO.push({ id: 'ch', page: 'health', title: '体检场景', options: [['mixed', '有问题'], ['stale', 'cron 上报过期'], ['never', 'admin 从未上报']], get: () => CH.scenario, set: (v) => { CH.scenario = v; } });
const LV = { ok: ['ok', 'check', '正常'], warn: ['warn', 'warn', '注意'], bad: ['bad', 'fail', '有问题'], unknown: ['', 'help', '未知'] };
function chProcesses() {
  const web = { process: 'web', title: '网站服务', host: 'katrain-web-7f2c', build: 'a41c9e2', age: 3, checks: [['database', 'ok', 'PostgreSQL 主库'], ['mode', 'ok', '服务器模式'], ['billing', 'bad', '计费闸已开但每周免费报告不为 0（手机绑定与限流未上线前必须为 0）'], ['cloud_katago', 'ok', '已配置云端分析引擎'], ['storage', 'ok', '媒体存对象存储'], ['credentials', 'bad', '数据库或对象存储密码仍是示例默认值']] };
  const cron = { process: 'cron', title: '定时任务', host: 'katrain-cron-19ab', build: 'a41c9e2', age: CH.scenario === 'stale' ? 47 : 6, checks: [['database', 'ok', 'PostgreSQL 主库'], ['katago', 'ok', '已配置分析引擎地址'], ['translation', 'warn', '未配置翻译服务密钥：直播名称翻译失效'], ['credentials', 'bad', '数据库密码仍是示例默认值']] };
  const admin = { process: 'admin', title: '管理后台', host: 'katrain-admin-0c1d', build: 'a41c9e2', age: 1, checks: [['database', 'ok', 'PostgreSQL 主库'], ['credentials', 'bad', '数据库或对象存储密码仍是示例默认值']] };
  if (CH.scenario === 'never') admin.never = true;
  if (CH.scenario === 'stale') cron.stale = true;
  return [web, cron, admin];
}
pages.health = {
  render() {
    const ps = chProcesses();
    const all = ps.filter((p) => !p.stale && !p.never).flatMap((p) => p.checks);
    const n = (l) => all.filter((c) => c[1] === l).length;
    const version = ps.some((p) => p.stale || p.never) ? ['unknown', '不是每个进程都有新近上报，无法比较版本'] : ['ok', '三个进程运行同一构建版本 a41c9e2'];
    const card = (p) => {
      const state = p.never ? ['bad', '从未上报'] : p.stale ? ['warn', `上报已过期 · ${p.age} 分钟前`] : ['ok', `${p.age} 分钟前`];
      return `<section class="panel ch-card ${p.stale || p.never ? 'dim' : ''}"><div class="panel-head"><h2>${p.title}<small class="mono">${p.process}</small></h2><span class="chip ${state[0]}">${state[1]}</span></div>
        <div class="ch-meta">${p.never ? '<span>这个进程还没有写过体检结果。可能未部署新版本，或进程没在运行。</span>' : `<span>主机 <b class="mono">${p.host}</b></span><span>版本 <b class="mono">${p.build}</b></span>`}</div>
        ${p.never ? '' : p.stale ? '<div class="ch-stale">超过 30 分钟没有更新，结论不再可信，已隐藏。只保留最后上报时间。</div>' : `<ul class="ch-list">${p.checks.map(([id, l, m]) => `<li class="${LV[l][0]}">${ic(LV[l][1])}<span>${m}<small class="mono">${id}</small></span><em>${LV[l][2]}</em></li>`).join('')}</ul>`}</section>`;
    };
    return `<main class="lab-page"><div class="lab-heading"><div><h1>配置体检</h1><p>各进程定时自查生效配置，只上报结论、不上报配置值</p></div><span class="lab-status">${ic('refresh')}每 10 分钟上报 · 30 分钟未更新视为过期</span></div>
      <div class="lab-content"><section class="panel ch-summary"><div class="ch-counts"><span class="chip bad">${ic('fail')}${n('bad')} 项有问题</span><span class="chip warn">${ic('warn')}${n('warn')} 项注意</span><span class="chip ok">${ic('check')}${n('ok')} 项正常</span></div><div class="ch-cross ${version[0]}">${ic(LV[version[0]][1])}<span>版本一致性：${version[1]}</span></div><button class="btn small">${ic('refresh')}刷新</button></section>
        <div class="ch-grid">${ps.map(card).join('')}</div>
        <p class="note">不检查：SECRET_KEY（能上报就已通过启动闸）、外部服务是否连通（KataGo /health 会报假绿）、性能监控。</p></div></main>`;
  },
};

// ---------- 报错追踪 ----------
const ER = { status: 'open', selected: 1, scenario: 'normal' };
PROTO.push({ id: 'er', page: 'errors', title: '报错场景', options: [['normal', '有报错'], ['empty', '没有报错'], ['silent', 'cron 采集器失联']], get: () => ER.scenario, set: (v) => { ER.scenario = v; } });
const ERRORS = [
  { id: 1, process: 'web', count: 214, template: 'Engine request failed for session %s', exc: 'httpx.ReadTimeout', loc: 'engine_client.py:analyze < router.py:route < games.py:play', last: '3 分钟前', first: '2026-09-26 21:04', build: 'a41c9e2', fresh: true, sample: 'Engine request failed for session 8f1c…\nTraceback (most recent call last):\n  File "katrain/web/core/engine_client.py", line 212, in analyze\n    resp = await client.post(url, json=payload, timeout=30)\nhttpx.ReadTimeout: timed out' },
  { id: 2, process: 'cron', count: 17, template: 'translate batch failed: %s', exc: 'KeyError', loc: 'translator.py:translate_batch < live_sync.py:run', job: 'translate_names', last: '26 分钟前', first: '2026-09-25 08:40', build: 'a41c9e2', reopened: true, sample: "translate batch failed: 'output'\nTraceback …\nKeyError: 'output'" },
  { id: 3, process: 'web', count: 3, template: 'SMS provider rejected request for <phone>', exc: null, loc: 'auth.py:request_sms', last: '5 小时前', first: '2026-09-27 04:12', build: 'a41c9e2', sample: 'SMS provider rejected request for <phone> key=<redacted>' },
];
pages.errors = {
  render() {
    const list = ER.scenario === 'empty' ? [] : ERRORS;
    const g = list.find((e) => e.id === ER.selected) || list[0];
    const col = [['web', '网站服务', '12 秒前刷写 · 丢弃 0', 'ok'], ['cron', '定时任务', ER.scenario === 'silent' ? '上报已过期 · 52 分钟前' : '8 秒前刷写 · 丢弃 0', ER.scenario === 'silent' ? 'warn' : 'ok'], ['admin', '管理后台', '3 秒前刷写 · 丢弃 0', 'ok']];
    const blind = col.some((c) => c[3] !== 'ok');
    const rows = list.map((e) => `<button class="er-row ${e.id === g?.id ? 'on' : ''}" data-act="er-pick" data-id="${e.id}"><span class="er-count">${e.count}</span><span class="er-main"><strong>${esc(e.template)}</strong><small class="mono">${e.exc ? e.exc + ' · ' : ''}${e.loc}</small></span><span class="er-side"><span class="chip">${e.process}</span>${e.fresh ? '<span class="chip bad">新</span>' : e.reopened ? '<span class="chip warn">重新出现</span>' : ''}<small>${e.last}</small></span></button>`).join('');
    const detail = g ? `<section class="panel er-detail"><div class="panel-head"><h2>${esc(g.template)}</h2><button class="btn small" data-act="er-resolve">${ic('check')}标记已解决</button></div>
      <dl class="er-facts"><div><dt>进程</dt><dd>${g.process}${g.job ? ` · 任务 ${g.job}` : ''}</dd></div><div><dt>次数</dt><dd>${g.count}</dd></div><div><dt>首次</dt><dd>${g.first}</dd></div><div><dt>最近</dt><dd>${g.last}</dd></div><div><dt>版本</dt><dd class="mono">${g.build}</dd></div></dl>
      <div class="er-loc"><span class="note">位置（最内三帧）</span><code>${g.loc}</code></div><pre class="er-sample">${esc(g.sample)}</pre><p class="note er-pad">样本已脱敏（手机号、邮箱、令牌、key= / password=），不含请求体与请求头。再次出现会自动重新打开。</p></section>` : `<section class="panel"><div class="empty-view">${ic(blind ? 'warn' : 'check')}<span>${blind ? '有采集器未在上报，不能据此判断没有报错' : '没有未解决的报错'}</span></div></section>`;
    return `<main class="lab-page"><div class="lab-heading"><div><h1>报错追踪</h1><p>网站、定时任务、后台三个进程的 ERROR 日志，按指纹聚合</p></div><span class="lab-status">${ic('info')}保留 30 天 · 最多 5000 组 · 告警只在后台内提示</span></div>
      <div class="lab-content"><section class="panel er-collectors">${col.map(([id, t, m, l]) => `<span class="er-col ${l}">${ic(l === 'ok' ? 'check' : 'warn')}<b>${t}</b><small>采集器 · ${m}</small></span>`).join('')}</section>
        <div class="er-grid"><section class="panel er-list"><div class="panel-head"><div class="seg">${[['open', '未解决'], ['resolved', '已解决'], ['all', '全部']].map(([v, t]) => `<button aria-pressed="${ER.status === v}" data-act="er-status" data-v="${v}">${t}</button>`).join('')}</div><select class="er-proc" aria-label="进程"><option>全部进程</option><option>web</option><option>cron</option><option>admin</option></select></div>
          ${rows || `<div class="empty-view"><small>${blind ? '有采集器失联：列表为空不代表没有报错' : '没有未解决的报错'}</small></div>`}<div class="ub-pager"><span class="note">${list.length} 组 · 按最近出现排序</span></div></section>${detail}</div></div></main>`;
  },
};
actions['er-pick'] = (el) => { ER.selected = +el.dataset.id; render(); };
actions['er-status'] = (el) => { ER.status = el.dataset.v; render(); };
actions['er-resolve'] = () => { render(); };
