import json, re

MAP = {
  'dashboard': ['首页 · Dashboard（模块入口网格）'],
  'play-menu': ['对局 · PlayMenu（模式选择）'],
  'ai-setup-rated': ['升降级对弈 · 页面外壳 (isRated 分支)', '升降级对弈 · 状态加载失败',
                     '升降级对弈 · 主卡 · 本局挑战(可开新局)', '升降级对弈 · 主卡 · 未完成对局(有一局挡着)',
                     '升降级对弈 · 主卡 · 成绩还没送到云端(旧云端兜底格)', '升降级对弈 · 主卡 · 右栏结算已完成(回执)'],
  'ai-setup-free': ['自由对弈设置 (free play 大表单)'],
  'research': ['研究 · L1 编辑/摆盘模式 (setup)', '研究 · L2 分析进行中 (progress)',
               '研究 · L3 分析结果 (analysis result)', '研究 · 棋谱库弹窗 (GameLibraryModal)'],
  'tsumego-levels': ['死活题 · 难度列表（主界面）'],
  'tsumego-categories': ['死活题 · 题型列表（主界面 / 空态同版式）'],
  'tsumego-units': ['死活题 · 单元列表（主界面）'],
  'tsumego-list': ['死活题 · 题目九宫格（主界面）'],
  'tsumego-problem': ['死活题 · 解题（桌面·默认未解出）', '死活题 · 解题（移动·默认未解出）'],
  'kifu': ['棋谱库 · 列表就绪（未选中棋谱）', '棋谱库 · 棋谱预览（棋盘 + 播放控制 + 在研究中打开）',
           '棋谱库 · 空结果', '棋谱库 · 列表加载中（骨架屏）', '棋谱库 · 右栏预览加载中'],
  'hvh-lobby': ['人人对弈 · 大厅（默认已加载视图）', '人人对弈 · 匹配中弹窗', '人人对弈 · 收到对局邀请弹窗',
                '人人对弈 · 大厅（在线玩家加载失败）', '人人对弈 · 大厅（全空态）'],
  'game-room': ['对局室 · 棋手视角 · 2D · 对局进行中', '对局室 · 观战者视角', '对局室 · 3D 视图（含 3D 加载中）',
                '对局室 · 对局已结束（终局/复盘态）', '对局室 · 离开确认弹窗', '对局室 · 认输确认弹窗',
                '对局室 · 数子确认弹窗（发起方）', '对局室 · 数子请求弹窗（应答方）', '对局室 · 对局结束弹窗',
                '对局室 · 加载失败'],
  'game-rated': ['AI 对弈 · 升降级分支（isRated → BoardPageShell 模板）', 'AiLadderSettlementPanel(对局页右栏结算面板)'],
  'game-free': ['AI 对弈 · 自由分支（free / legacy 双栏布局）'],
  'reports': ['复盘 · 主界面（已登录，有棋局）', '复盘 · 棋局卡片（组件全状态）', '复盘 · 导入下拉菜单',
              '复盘 · 从本地导入 SGF 弹窗', '复盘 · 删除确认弹窗', '复盘 · 空列表 / 搜索无结果', '复盘 · 列表/预览加载中'],
  'report-detail': ['报告详情 · 主界面', '报告详情 · 加载失败', 'AI 推荐面板 · 有分析数据',
                    '走势图 · 走势页（tab 0）', '走势图 · 妙手页（tab 1）', '走势图 · 失误页（tab 2）',
                    '回放控制条（组件，两处复用）'],
  'live-list': ['直播 · 列表页(精选对局 Tab,已选中对局)', '直播 · 列表页 赛事预告 Tab',
                '直播 · 列表页 加载中', '直播 · 列表页 空态 / 未选择对局'],
  'live-match': ['直播 · 对局页 · 直播中(APPROVED TEMPLATE)', '直播 · 对局页 · 已结束(复盘态)',
                 '直播 · 对局页 加载中(骨架屏)', '直播 · 对局页 加载失败',
                 '直播 · 显示控制条(LiveMatchDisplayControls 组件全分支)',
                 '直播 · AI 推荐 AiAnalysis(有分析 / 无分析两态)',
                 '直播 · 走势 / 妙手 / 失误 TrendChart(三 tab + 两空态)',
                 '直播 · 播放控制条 PlaybackBar(live / finished / touchSized 三态)'],
  'tutorial-landing': ['教程 · 分类首页 — 正常', '教程 · 分类首页 — 加载失败'],
  'tutorial-books': ['教程 · 书籍列表 — 正常 / 空态', '教程 · 书籍列表 — 加载失败'],
  'tutorial-book': ['书籍详情 · 目录 — 正常（章节手风琴）', '书籍详情 · 全屏视频对话框', '书籍详情 · 目录 — 加载失败'],
  'tutorial-figure': ['变化图 · L1 只读模式（三栏）', '变化图 · L2 编辑模式（棋盘编辑工具栏）',
                      '变化图 · 图形子菜单（Menu 打开态）', '变化图 · 讲解编辑模式（第三列）',
                      '变化图 · 识别流程调试面板', '变化图 · 无棋盘数据（初始化空棋盘）', '变化图 · 加载失败'],
}

inv = json.load(open('inventory.json'))
ren = json.load(open('rendered.json'))


def norm(s):
    s = re.sub(r'[（(].*?[)）]', '', s or '')
    s = re.sub(r'\s+', '', s)
    for junk in ('(icononly)', '—', '·'):
        s = s.replace(junk, '')
    return s.strip()


def labels_of(c):
    out = []
    for k in ('chinese', 'label'):
        v = c.get(k) or ''
        if not v or 'no cn' in v or v.strip().upper() in ('NONE', 'N/A'):
            continue
        for part in re.split(r'\s*/\s*|\s*；\s*|\s*，\s*', v):
            p = norm(part)
            if p and len(p) < 24:
                out.append(p)
    return out


SKIP_KINDS = {'canvas', 'video', 'audio', 'other'}
total = 0
missing_total = 0
report = []
for sid, invnames in MAP.items():
    rendered = set(norm(x) for x in ren.get(sid, []))
    miss = []
    seen = set()
    for name in invnames:
        s = inv.get(name)
        if not s:
            report.append('!! inventory screen not found: ' + name)
            continue
        for c in s.get('controls', []):
            if c['kind'].split('（')[0].strip() in SKIP_KINDS:
                continue
            labs = labels_of(c)
            if not labs:
                continue
            key = labs[0]
            if key in seen:
                continue
            seen.add(key)
            hit = any(any(l in r or r in l for r in rendered) for l in labs)
            if not hit:
                miss.append('%s [%s] %s' % (labs[0], c['kind'][:12], name.split('·')[-1].strip()[:20]))
    total += len(seen)
    missing_total += len(miss)
    if miss:
        report.append('')
        report.append('### %s: %d / %d 未渲染' % (sid, len(miss), len(seen)))
        for m in miss:
            report.append('    - ' + m)

print('checked %d inventoried controls; %d not found in the prototype' % (total, missing_total))
print('\n'.join(report))
