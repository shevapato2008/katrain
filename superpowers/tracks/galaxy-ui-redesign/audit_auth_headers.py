# -*- coding: utf-8 -*-
"""通查闸：后端要求鉴权的端点 × 前端调用时到底会不会带上 Authorization。

背景（2026-08-21 排查「研究 → 开始研究 卡在『正在连接研究会话…』」时定位到的）：
后端 72 个端点挂着 Depends(get_current_user)；box_sso.resolve_http_token 在非严格档
是 `cookie or header`，而那块 sb_token cookie 只在 hostname == 127.0.0.1 时才发
（auth.py _issue_loopback_sso_cookie）。所以前端不带 header 的调用在本机一路绿灯，
一上 go.sailorvoyage.top / modelstella.com 就整片 401 —— 而且轮询把异常吞了，
界面只会一直转圈。

判据不是「调用点有没有写 token」，是「这次调用最终会不会带上 Authorization」：
  · 走 apiPost / apiGet → 安全（api.ts 的 authHeaders 会兜底取 localStorage token）
  · 手写 fetch('/api/...') → 必须在同一段里用 authHeaders，否则算漏
新增手写 fetch 打到需要鉴权的端点，这条闸会红。

用法：python3 superpowers/tracks/galaxy-ui-redesign/audit_auth_headers.py
退出码 0 = 干净。
"""
import re, pathlib, json, sys

ROOT = pathlib.Path('katrain/web')

# ── 1. 后端：路由 → 是否需要鉴权 ────────────────────────────────
route_re = re.compile(r'@(?:app|router)\.(get|post|put|delete|patch)\(\s*[fr]?["\']([^"\']+)["\']')
guarded = {}          # path -> {'methods': set, 'auth': 'required'|'optional'}
for py in ROOT.rglob('*.py'):
    src = py.read_text(encoding='utf-8', errors='replace')
    lines = src.split('\n')
    for i, line in enumerate(lines):
        m = route_re.search(line)
        if not m:
            continue
        method, path = m.group(1).upper(), m.group(2)
        # 函数签名可能跨行，往下看 20 行到函数体开始
        sig = []
        for j in range(i + 1, min(i + 22, len(lines))):
            sig.append(lines[j])
            if re.search(r'\)\s*(->[^:]*)?:\s*$', lines[j]):
                break
        sig = '\n'.join(sig)
        if 'get_current_user_optional' in sig:
            auth = 'optional'
        elif 'get_current_admin_user' in sig:
            auth = 'admin'
        elif 'get_current_user' in sig:
            auth = 'required'
        else:
            auth = 'none'
        prefix = ''
        # api/v1 的 router 有前缀，从 include_router 里找
        rec = guarded.setdefault(prefix + path, {'methods': set(), 'auth': set(), 'file': set()})
        rec['methods'].add(method)
        rec['auth'].add(auth)
        rec['file'].add(str(py.relative_to(ROOT)))

# ── 2. 前端：调用点 → 有没有带 token ────────────────────────────
UI = pathlib.Path('katrain/web/ui/src')
calls = []
call_re = re.compile(r'(apiPost|apiGet|fetch)\(\s*[`"\']([^`"\']*?)[`"\'\?]', re.S)
for ts in list(UI.rglob('*.ts')) + list(UI.rglob('*.tsx')):
    if '.test.' in ts.name:
        continue
    src = ts.read_text(encoding='utf-8', errors='replace')
    for m in call_re.finditer(src):
        kind, path = m.group(1), m.group(2)
        if not path.startswith('/api'):
            continue
        # 取这次调用的整段：从左括号起按括号配对扫到闭合处。
        # 之前用「往后 500 字符」的窗口，会串到下一个恰好带 token 的函数上，
        # 把真正不带 token 的调用漏掉（analysisScan 就是这么漏的）。
        open_at = src.index('(', m.start())
        depth, k = 0, open_at
        while k < len(src):
            if src[k] == '(':
                depth += 1
            elif src[k] == ')':
                depth -= 1
                if depth == 0:
                    break
            k += 1
        seg = src[open_at:k + 1]
        # apiPost / apiGet 自带鉴权头（api.ts authHeaders 兜底），一律算安全；
        # 手写 fetch 必须自己用上 authHeaders 才算安全。
        if kind in ('apiPost', 'apiGet'):
            has_token = True
        else:
            # headers 对象通常在 fetch 上面一两行拼好，所以往前多看 12 行
            back = src[max(0, m.start() - 600): m.start()]
            near = back[back.rfind('\n', 0, max(0, len(back) - 1)) - 600:] if back else ''
            probe = seg + '\n' + '\n'.join(back.split('\n')[-12:])
            has_token = ('authHeaders' in probe) or ('Authorization' in probe) or ('Bearer' in probe)
        calls.append({'file': str(ts.relative_to(UI)), 'kind': kind, 'path': path,
                      'token': bool(has_token),
                      'line': src[:m.start()].count('\n') + 1})

# ── 3. 交叉 ────────────────────────────────────────────────────
def norm(p):
    return re.sub(r'\{[^}]+\}', '{}', p.rstrip('/'))

backend = {norm(k): v for k, v in guarded.items()}
problems = []
for c in calls:
    p = norm(c['path'])
    hit = backend.get(p)
    if hit is None:
        # 前端路径里可能拼了变量，退化成前缀匹配
        cands = [k for k in backend if p.startswith(k) and len(k) > 8]
        hit = backend[max(cands, key=len)] if cands else None
    if hit and 'required' in hit['auth'] and not c['token']:
        problems.append({**c, 'backend': sorted(hit['file'])[:1], 'methods': sorted(hit['methods'])})

print('后端路由总数 %d ；其中需要鉴权 %d' % (
    len(backend), sum(1 for v in backend.values() if 'required' in v['auth'])))
print('前端 /api 调用点 %d ；其中不带 token %d' % (len(calls), sum(1 for c in calls if not c['token'])))
print('\n【要求鉴权 × 前端不带 token】共 %d 处：' % len(problems))
seen = set()
for pr in sorted(problems, key=lambda x: (x['path'], x['file'])):
    key = (pr['path'], pr['file'], pr['line'])
    if key in seen:
        continue
    seen.add(key)
    print('  %-46s  %s:%d' % (pr['path'], pr['file'], pr['line']))

import sys as _sys
_sys.exit(1 if problems else 0)
