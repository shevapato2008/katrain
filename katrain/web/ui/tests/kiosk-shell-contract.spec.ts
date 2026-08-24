import { expect, test } from '@playwright/test';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * 契约闸:**扫源码,不开浏览器**。守的是几条「本地看着对、上板才塌」的规矩,
 * 眼睛和尺子都验不出来 —— 四图对比看不出一个 `50vh`,几何闸也量不出来
 * (它在 1024×600 下量,而 `50vh` 在 1024×600 下恰好等于 300px,一点不差)。
 *
 * 两条都是**基线名单**,不是一刀切:`src/kiosk` 现存 45 个文件用 MUI 图标、
 * 18 个文件用视口单位,本轮不去大改它们(那是十屏 Task 一屏一屏做的事)。
 * 断言写成**全等**而不是「没有新增」——名单里的文件被清干净了、却忘了从名单里划掉,
 * 一样要红。名单只许缩,不许悄悄留着一条已经不成立的账。
 *
 * 变异记录(2026-08-20,Task 6 Step 7),**三支各演示一次**:
 *   ① 往 `shell/KioskSecLabel.tsx` 里塞一句 `height: "50vh"`
 *      ⇒ 闸一红,Received 多出 "src/kiosk/shell/KioskSecLabel.tsx"。
 *   ② 往同一个文件顶上加 `import { Gear } from '@mui/icons-material'`
 *      ⇒ 闸二红,同样多出那一行。
 *   ③ 把白名单里的 `SubPageBar.tsx` 的 MUI 图标 import 改掉(相当于"清干净了但没划掉")
 *      ⇒ 闸二红,Expected 多出那一行 —— 这一支证明名单**只许缩**。
 *      ⚠️ 第一次做这个变异时把 `@mui/icons-material` 改成 `@mui/icons-material-REMOVED`,
 *      正则是子串匹配、照样命中,闸绿了。**变异本身没生效不等于闸没牙**——
 *      改成 `@mui/ICONS-GONE` 才真的移走了那个子串。
 */

// ESM 里没有 __dirname。用 process.cwd() 也行(playwright 从 ui/ 起),
// 但那样这份 spec 就依赖「从哪儿敲的命令」——钉在文件自己的位置上更稳。
const UI = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const rel = (p: string) => relative(UI, p).split('\\').join('/');

function walk(dir: string, pick: (p: string) => boolean): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = resolve(dir, e.name);
    if (e.isDirectory()) { out.push(...walk(p, pick)); continue; }
    if (pick(p)) out.push(p);
  }
  return out;
}

/**
 * 扫描类的闸**必须说清扫的是代码还是文本** —— 不说清就会把散文当缺陷。
 *
 * 2026-08-23 从象棋那支的实测里搬来的判据(他们那条新扫描闸把示例代码写进了自己的
 * docstring,还原变异之后照样红)。**搬的是判据,不是他们的做法** ——
 * 他们连字符串字面量一起抹掉,因为他们找的是 `now + 900` 那种**算术**;
 * 这里两条闸找的东西**恰恰住在字符串里**(`from '@mui/icons-material'`、`height: '50vh'`),
 * 照抄会让两条闸一起变成永远绿的空闸。⇒ **只抹注释,不动字符串。**
 *
 * 本文件的闸三(`t(key, 默认值)`)早就在自己那儿抹注释了 —— 同一个文件里两种扫描面,
 * 那本身就是个味道。三条现在走同一个 `codeOnly`。
 *
 * 行号不保留:这三条闸报的是**文件名**,不报行。要报行的时候得换成保号的抹法。
 *
 * **四条分支各跑过一次**(2026-08-23,拿 `utils/playInput.ts` 和 `shell/KioskOptSeg.tsx`
 * 这两个干净文件当靶子):
 *   ① 闸一红:真代码里加 `height: '50vh'` ⇒ 红。
 *   ② 闸一**该绿**:块注释里写一行 `height: 50vh,后来撤了` ⇒ 新扫描面绿。
 *      **拿 HEAD 的旧扫描面重跑同一处变异 ⇒ 红**,Received 多出 `utils/playInput.ts`
 *      —— 旧的按行判注释漏掉了「块注释里不以 `*` 开头的中间行」。
 *   ③ 闸二红:真 `import { Gear } from '@mui/icons-material'` ⇒ 红。
 *   ④ 闸二**该绿**:行注释里写「别从 `@mui/icons-material` 引图标」⇒ 新扫描面绿。
 *      **旧扫描面重跑 ⇒ 红**,Received 多出 `shell/KioskOptSeg.tsx`。
 * ②④ 那两条假红最可能的收场是「把这个文件加进白名单」—— 而两条闸都是 `toEqual` 的
 * 单向棘轮,加进去之后棘轮就永远带着一条**不成立**的账。这才是这次要修的东西。
 */
function codeOnly(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, ' ')     // 块注释(TSX 与 CSS 通用)
    .replace(/^[ \t]*\/\/.*$/gm, ' ');       // 整行的行注释
}

/* ─────────────────────────────────────────────────────────────────────────
 * 闸一:固定 1024×600 画布上不许出现 vw / vh / cqw / cqh
 *
 * 一相对化,「切模块不跳」就没法用截图证明了 —— 同一份代码在 Mac 全屏和盒子 7 寸屏上
 * 算出来的是两个尺寸,而我们的整套验收(四图对比 + 几何闸)都建立在
 * 「1024×600 画布里的 px 就是屏上的 px」这一条上。
 *
 * `RotationWrapper.tsx` 是**永久豁免**:它在画布**外面**,职责就是把整个视口铺满
 * 再按方向旋转,`100vw/100vh` 正是它该写的东西。KioskFrame 在它里面按 min(w/1024, h/600)
 * 缩放 —— 那一层才是画布。
 *
 * 划账记录:
 *   Task 4 —— `components/layout/navTabs.tsx` 随旧 Dock 一起删,从图标名单里划掉。
 *             (这一笔就是这道闸自己抓出来的:它红了,而不是等着谁想起来手动更新。)
 * ────────────────────────────────────────────────────────────────────────── */
// Task 12(2026-08-22):`TsumegoPage.tsx` 两处基线一起划掉 —— 屏 11 按稿子重写之后,
// 那个 `height:'50vh'` 的加载转圈和 `ArrowForward` 一起没了(棘轮往下走,不是往上加)。
// Task 13b(2026-08-22):`TsumegoUnitListPage.tsx` 同理 —— 屏 13 按稿子重画成 `.qgrid`,
// 那个 `height:'50vh'` 的转圈换成了 `.empty` 三态。
const VIEWPORT_UNIT_BASELINE = [
  'src/kiosk/__tests__/RotationWrapper.test.tsx',
  'src/kiosk/components/guards/KioskAuthGuard.tsx',
  'src/kiosk/components/layout/RotationWrapper.tsx',
  'src/kiosk/components/report/ReportLibraryImportDialog.test.tsx',
  'src/kiosk/components/report/ReportLibraryImportDialog.tsx', // (C) 对话框
  'src/kiosk/components/report/ReportLocalImportDialog.test.tsx',
  'src/kiosk/components/report/ReportLocalImportDialog.tsx', // (C) 对话框
  'src/kiosk/components/research/CloudSGFPanel.tsx', // (A) 研究屏
  'src/kiosk/components/tsumego/SuccessOverlay.tsx', // (C) 做题屏上的浮层
  'src/kiosk/pages/TsumegoCategoriesPage.tsx', // (B) 训练营分类,未排
  'src/kiosk/pages/TsumegoLevelPage.tsx',
  'src/kiosk/pages/TutorialBookDetailPage.tsx', // (B) 屏 24 课程书目,未排
  'src/kiosk/pages/TutorialBooksPage.tsx',
  'src/kiosk/pages/TutorialSectionPage.tsx', // (B) 屏 25 课程小节,未排
];

test('固定画布上不许新增 vw / vh / cqw / cqh', () => {
  const files = walk(resolve(UI, 'src/kiosk'), (p) => /\.(tsx?|css)$/.test(p));
  // 原来这里是**按行**判注释(`t.startsWith('*') || '//' || '/*'`)—— 漏两种:
  // 代码行尾巴上挂的注释,和块注释里不以 `*` 开头的中间行。换成整份抹一遍。
  const hit = files.filter((p) => /[0-9](vw|vh|cqw|cqh)\b/.test(codeOnly(readFileSync(p, 'utf8'))))
    .map(rel).sort();
  expect(hit).toEqual(VIEWPORT_UNIT_BASELINE);
});

/* ─────────────────────────────────────────────────────────────────────────
 * 闸二:图标只能从 `kiosk-shell/icons/` 出(规范 §10)
 *
 * 四个前端要用**同一份字节**。MUI 的 Material 图标和 Phosphor 不是同一套线宽、
 * 同一套圆角,混着用的结果是「从对弈切到训练营,图标风格换了一次」——
 * 又一种「切模块不跳」的破法。
 *
 * 手写 `<path d="…">` 同罪:它绕过 MANIFEST,谁也说不清那一笔是从哪儿来的。
 * ────────────────────────────────────────────────────────────────────────── */
// 2026-08-22(Task 11)一次摘掉四条,它们都是**已经清干净的**,不是放行:
//   `SubPageBar.tsx` Task 8 删了整个文件;`PlayPage.tsx` Task 10 重画时换成了 `shell/icons`;
//   `VisionSetupPage.tsx` 早先某次顺手清掉、名单没跟;`GameControlPanel.tsx` 本 Task 重画。
// ⚠️ **前三条说明这条闸在 Task 8 之后就一直是红的** —— 它是 `toEqual` 的双向棘轮:
// 名单只许缩,而**缩了不改名单一样红**。那正是它该有的样子(名单和现实不许漂),
// 但也意味着「上一轮全绿」那句话在这一条上不成立,记在这里免得下一个人再查一遍。
// 2026-08-22(Task 12)再摘一条:`TsumegoPage.tsx` 按稿子重写,`ArrowForward` 换成了共享外壳的药丸键。
// 2026-08-22(屏 14)再摘两条:做题屏按稿子重画,九个 MUI 图标换成 `shell/icons` 的动作区;
// `PhysicalModeToggle.tsx` 整个文件删了 —— 「实体棋盘」成了共享开关排里的一个 `role="switch"`。
// 2026-08-23(屏 15/16/19/20/23/27)一路摘掉六条:`KifuPage` / `ReportsPage` / `ReportImportMenu`
// / `ReportDetailPage` / `SettingsPage` / `AccountSection`,外加整块删掉的 `ReportMetaPanel`。
//
// ── 2026-08-23(Task 20 Step 1)把剩下的按**为什么还在**分了三类 ──────────────
// 名单不是「以后再说」的清单,是「这些为什么允许」的记录。三类,判据各不相同:
//
//  (A) **D2 稿外五屏的内容区** —— 摆谱 / 直播 / 研究 / 跨平台 / 标定。
//      稿子没画这五屏,D2 明写「只接壳,不推导版式」:没有参照物就没有四图闸,
//      重画它们的内容区等于自己发明设计。**允许留着,直到稿子把它们补齐。**
//
//  (B) **稿子画了、但本轮的十个 Task 没排到的屏** —— 在线大厅、训练营分类、课程书目、课程小节。
//      它们在 `sample-go/build.py` 的进度带上仍是「外壳已接」。
//      **允许留着,直到那几屏各自被重画。**
//      2026-08-23 屏 02/03 重画时摘掉 `AiSetupPage.tsx`,屏 04 重画时摘掉 `PvpLocalSetupPage.tsx`
//      (它同时从下面那条 PO 名单里带走 `Black` / `White` 两条 —— 那两句改成了
//      `setup:black_side` / `setup:white_side`,说的是**人**不是子)。
//      2026-08-24 屏 06 重画时摘掉 `LobbyPage.tsx`,同时从 PO 名单里带走它那**九条** ——
//      那九条全是「源码写 A、屏上出 B」的实例(`lobby:title` 写着「在线大厅」,
//      cn PO 却是「多人游戏大厅」),重画时逐条换成了这一屏自己的新 key。
//      2026-08-24 跨平台三屏(07 / 08 / 09)一起重画,三条一起摘掉。
//      这一轮之后名单里**再没有跨平台那一族**。
//
//  (C) **对话框与浮层** —— 它们不在 1024×600 的版式里(盖在上面),规范 §10 管的是屏上的
//      图标风格。**允许留着**,但重画所在的屏时顺手换掉最省事。
//
// 三类之外一个都不许有。新增一条 = 有人在**已经重画过的屏**上又引了 MUI 图标 ⇒ 该红。
const MUI_ICON_BASELINE = [
  'src/kiosk/__tests__/ModeCard.test.tsx', // (C) 测试文件,不上屏
  'src/kiosk/components/game/RecalibrationModal.tsx', // (C) 对局屏上的浮层
  'src/kiosk/components/physical/PhysicalPlayStatusChip.tsx', // (C) 对局屏上的浮层
  'src/kiosk/components/report/ReportGameCard.tsx', // (B) galaxy 侧还在用;kiosk 复盘屏已不用它
  'src/kiosk/components/report/ReportLibraryImportDialog.tsx',
  'src/kiosk/components/report/ReportLocalImportDialog.tsx',
  'src/kiosk/components/research/CloudSGFPanel.tsx',
  'src/kiosk/components/research/ResearchAnalysisPanel.tsx', // (A) 研究屏
  'src/kiosk/components/research/ResearchSetupPanel.tsx', // (A) 研究屏
  'src/kiosk/components/research/ResearchToolbar.tsx', // (A) 研究屏
  'src/kiosk/components/tsumego/PhysicalStatePanel.tsx', // (C) 做题屏上的浮层
  'src/kiosk/components/tsumego/SuccessOverlay.tsx',
  'src/kiosk/components/vision/AmbiguousStoneAlert.tsx', // (A) 标定/识别
  'src/kiosk/components/vision/GeometryCalibrationWorkspace.tsx', // (A) 标定屏
  'src/kiosk/components/vision/GeometryVideoPanel.tsx', // (A) 标定屏
  'src/kiosk/components/vision/VisionSyncOverlay.tsx', // (A) 标定/识别
  'src/kiosk/pages/BaipuListPage.tsx', // (A) 摆谱屏
  'src/kiosk/pages/GameHistoryPage.tsx', // (B) 已无入口,等 Fan 裁定是并进复盘还是删
  'src/kiosk/pages/GamePage.tsx', // (C) 屏 05 已重画;剩的是对话框里的图标
  'src/kiosk/pages/LiveMatchPage.tsx', // (A) 直播屏
  'src/kiosk/pages/LivePage.tsx', // (A) 直播屏
  'src/kiosk/pages/ResearchPage.tsx', // (A) 研究屏
  'src/kiosk/pages/TsumegoCategoriesPage.tsx',
  'src/kiosk/pages/TutorialBookDetailPage.tsx',
  'src/kiosk/pages/TutorialSectionPage.tsx',
];

test('图标不许新增手写内联路径或 MUI 图标 —— 只能从 kiosk-shell/icons/ 出', () => {
  const files = walk(resolve(UI, 'src/kiosk'), (p) => p.endsWith('.tsx'));
  const hit = files.filter((p) => {
    if (p.endsWith('shell/icons.tsx')) return false;          // 它就是那个出口
    // 2026-08-23 之前这里扫的是**生文本**:注释里提一句「别引 `@mui/icons-material`」
    // 就会把一个干净的文件报成缺陷 —— 而这条闸是 `toEqual` 的单向棘轮,
    // 那种假红最可能被「加进白名单」收场,棘轮从此带着一条不成立的账。
    const src = codeOnly(readFileSync(p, 'utf8'));
    return /@mui\/icons-material/.test(src) || /<path\s+d="/.test(src);
  }).map(rel).sort();
  expect(hit).toEqual(MUI_ICON_BASELINE);
});

/* ─────────────────────────────────────────────────────────────────────────
 * 闸三:`t(key, 默认值)` 的**占位符约定必须和 PO 里那条一致**
 *
 * ⚠️ 这条是 2026-08-22(Task 13)踩出来的,不是想出来的。新写的卡片用了
 *     t('tsumego:unit', '第 {n} 单元').replace('{n}', …)
 * 而 `tsumego:unit` 在 cn PO 里是 **`单元`**(galaxy 三处在用)。
 * `t()` 的实现是 `translations[key] || defaultText` —— **翻译表赢**,于是拿到的是「单元」,
 * `.replace('{n}', …)` 找不到东西可换,**数字连同占位符一起人间蒸发**,屏上只剩「单元」。
 * 同一次还有另一半:`t('tsumego:problemRange', '第 {a} – {b} 题')` —— PO 里那条的占位符叫
 * `{start}/{end}`,于是 `{start}-{end}` **原样留在屏上**。
 *
 * 两半的表现相反,所以要两条闸:
 *   · 「原样留在屏上」→ `tests/kiosk-copy-placeholders.spec.ts`(真浏览器扫 innerText);
 *   · 「连数字一起消失」→ **就是这一条**(比源码里的默认值和 PO 里那条的占位符集合)。
 * 只有前一条时,把 `unit_n` 改回 `unit` 的变异**杀不死闸**(实测过):
 * 屏上是「单元」,一个花括号都没有,扫不出来。
 *
 * 单测同样抓不到这一类:jsdom 里翻译表没加载,`t()` 恒返回默认值,
 * 断言断的是「我自己和我自己一致」。
 * ────────────────────────────────────────────────────────────────────────── */
const PO = resolve(UI, '../../i18n/locales/cn/LC_MESSAGES/katrain.po');

/** 极简 PO 读法:只要 msgid/msgstr 成对的单行形式,够用 —— 这里只关心占位符名。 */
function readPo(path: string): Map<string, string> {
  const out = new Map<string, string>();
  const lines = readFileSync(path, 'utf8').split('\n');
  let id: string | null = null;
  for (const line of lines) {
    const mid = /^msgid\s+"(.*)"$/.exec(line.trim());
    if (mid) { id = mid[1]; continue; }
    const mstr = /^msgstr\s+"(.*)"$/.exec(line.trim());
    if (mstr && id !== null) { out.set(id, mstr[1]); id = null; }
  }
  return out;
}

const placeholders = (s: string) => new Set((s.match(/\{[A-Za-z_]\w*\}/g) ?? []));

test('t(key, 默认值) 的占位符必须和 cn PO 里那条一致 —— 不许拿旧 msgid 套新约定', () => {
  const po = readPo(PO);
  const files = walk(resolve(UI, 'src/kiosk'), (p) => /\.tsx?$/.test(p) && !p.endsWith('.test.tsx'));
  const bad: string[] = [];
  let scanned = 0;
  for (const p of files) {
    // 先把注释剥掉:注释里举的**反例**长得和真调用一模一样(这条闸自己的说明就写着一个),
    // 不剥的话它会指着一段解释说「你这儿写错了」——**闸把文档当成了代码**。
    const src = codeOnly(readFileSync(p, 'utf8'));
    for (const m of src.matchAll(/\bt\(\s*'([^'\\]+)'\s*,\s*'([^'\\]*)'\s*\)/g)) {
      const [, key, def] = m;
      const translated = po.get(key);
      if (translated === undefined) continue;          // PO 里没有 ⇒ 走默认值,不会打架
      scanned += 1;
      const a = placeholders(def);
      const b = placeholders(translated);
      if (a.size !== b.size || [...a].some((x) => !b.has(x))) {
        bad.push(`${rel(p)}  t('${key}', '${def}')  ←→ PO: "${translated}"`);
      }
    }
  }
  // 一条都没扫到 = 这条闸没有被测对象(正则写错、PO 路径错),会以「没有违规」的姿态变绿。
  expect(scanned, 'PO 里一个 key 都没对上 —— 这条闸没有被测对象').toBeGreaterThan(0);
  expect(bad, `占位符对不上(共扫了 ${scanned} 处 PO 里真有的 key)`).toEqual([]);
});

/* ─────────────────────────────────────────────────────────────────────────
 * 闸四:`t(key, 中文默认值)` 里**默认值和 PO 里那条说的不是一回事**
 *
 * ⚠️ 这条是 2026-08-22(屏 14)四图对比抓出来的,又一次:动作键写的是
 *     t('Undo', '退一手')
 * 而 cn PO 里 `Undo` 是「**悔棋**」—— `t()` 是 `translations[key] || defaultText`,
 * **翻译表赢**,屏上出现的是「悔棋」。同一次还有两处:`tsumego:practiceProblems`
 * 在 PO 里是一整句「练习死活题以提高计算能力」,被当页控条标题用;
 * `tsumego:loadError` 是一句「死活题库加载失败，请稍后重试。」,被当一个 `<h4>` 标题用。
 *
 * 和闸三是**同一个病、两种症状**:闸三管占位符对不上(数字会蒸发 / 花括号上屏),
 * 这一条管**词本身不一样** —— 源码上写着 A,屏上是 B,而两个都是中文、都通顺,
 * 所以读代码、跑单测(jsdom 里翻译表没加载,`t()` 恒返回默认值)都发现不了。
 *
 * 判据故意收窄成「**两边都是中文且不相等**」:默认值是英文时,那本来就是 msgid 的常态写法。
 *
 * 名单是**双向棘轮**:新增会红,修好了不改名单**一样红**。77 条是 2026-08-22 的实测存量,
 * 一条都不是本轮引入的 —— 本轮引入的三条当场改成了自己的 key。
 *
 * 变异实测(2026-08-22):把 `t('tsumego:undoMove', '退一手')` 改回 `t('Undo', '退一手')`,
 * 这条当场红,多出来的正是 `TsumegoProblemPage.tsx  Undo`。红分支跑过。
 * ────────────────────────────────────────────────────────────────────────── */
const PO_OVERRIDES_DEFAULT_BASELINE = [
  'src/kiosk/components/game/GameControlPanel.tsx  Black',
  'src/kiosk/components/game/GameControlPanel.tsx  White',
  'src/kiosk/components/report/ReportGameCard.tsx  report:deep',
  'src/kiosk/components/report/ReportGameCard.tsx  report:delete_game',
  'src/kiosk/components/report/ReportGameCard.tsx  report:generate_deep',
  'src/kiosk/components/report/ReportGameCard.tsx  report:generate_normal',
  'src/kiosk/components/report/ReportGameCard.tsx  report:no_result',
  'src/kiosk/components/report/ReportGameCard.tsx  report:normal',
  'src/kiosk/components/report/ReportGameCard.tsx  report:select_game',
  'src/kiosk/components/report/ReportGameCard.tsx  report:title_ai_free',
  'src/kiosk/components/report/ReportGameCard.tsx  report:title_ai_ranked',
  'src/kiosk/components/report/ReportGameCard.tsx  report:title_human',
  'src/kiosk/components/report/ReportGameCard.tsx  report:title_import',
  'src/kiosk/components/report/ReportGameCard.tsx  report:title_kifu',
  'src/kiosk/components/report/ReportImportMenu.tsx  report:import_local',
  'src/kiosk/components/report/ReportLibraryImportDialog.tsx  report:import_and_deep',
  'src/kiosk/components/report/ReportLibraryImportDialog.tsx  report:import_and_normal',
  'src/kiosk/components/report/ReportLibraryImportDialog.tsx  report:importing',
  'src/kiosk/components/report/ReportLibraryImportDialog.tsx  report:loading',
  'src/kiosk/components/report/ReportLibraryImportDialog.tsx  report:no_results',
  'src/kiosk/components/report/ReportLibraryImportDialog.tsx  report:search_placeholder_lib',
  'src/kiosk/components/report/ReportLocalImportDialog.tsx  report:choose_file_hint',
  'src/kiosk/components/report/ReportLocalImportDialog.tsx  report:import_and_deep',
  'src/kiosk/components/report/ReportLocalImportDialog.tsx  report:import_and_normal',
  'src/kiosk/components/report/ReportLocalImportDialog.tsx  report:import_local',
  'src/kiosk/components/report/ReportLocalImportDialog.tsx  report:importing',
  'src/kiosk/components/research/CloudSGFPanel.tsx  research:game_library',
  'src/kiosk/pages/AiSetupPage.tsx  Territory',
  'src/kiosk/pages/BaipuSessionPage.tsx  Black',
  'src/kiosk/pages/BaipuSessionPage.tsx  Undo',
  'src/kiosk/pages/BaipuSessionPage.tsx  White',
  'src/kiosk/pages/GameHistoryPage.tsx  Black',
  'src/kiosk/pages/GameHistoryPage.tsx  White',
  'src/kiosk/pages/GamePage.tsx  Black',
  'src/kiosk/pages/GamePage.tsx  White',
  'src/kiosk/pages/LiveMatchPage.tsx  Territory',
  'src/kiosk/pages/LivePage.tsx  Live',
  'src/kiosk/pages/ReportDetailPage.tsx  report:deep',
  'src/kiosk/pages/ReportDetailPage.tsx  report:login_required_detail',
  'src/kiosk/pages/ReportDetailPage.tsx  report:no_sgf',
  'src/kiosk/pages/ReportDetailPage.tsx  report:normal',
  'src/kiosk/pages/ReportDetailPage.tsx  report:territory',
  'src/kiosk/pages/ReportDetailPage.tsx  report:unknown_status',
  'src/kiosk/pages/ReportsPage.tsx  report:delete_confirm_body',
  'src/kiosk/pages/ReportsPage.tsx  report:delete_confirm_title',
  'src/kiosk/pages/ReportsPage.tsx  report:login_required',
  'src/kiosk/pages/ResearchPage.tsx  research:analyzing_game',
  'src/kiosk/pages/ResearchPage.tsx  research:cancel_analysis_warning',
  'src/kiosk/pages/ResearchPage.tsx  research:mode',
  'src/kiosk/pages/TsumegoCategoriesPage.tsx  tsumego:selectCategory',
  'src/kiosk/pages/TsumegoProblemPage.tsx  Black',
  'src/kiosk/pages/TsumegoProblemPage.tsx  White',
  // 2026-08-23(屏 04):用时那七档从 `AiSetupPage.tsx` 搬进 `utils/setupOptions.ts`(两屏共用),
  // 这一条**跟着文件走**,不是新漂的 —— `Byoyomi only 30s x3` 在 PO 里是「仅读秒」,
  // 而屏上要写「仅读秒 30秒×3」(轨上要看得见是几秒几次)。
  'src/kiosk/utils/setupOptions.ts  Byoyomi only 30s x3',
];

test('t(key, 中文默认值) 的默认值不许和 PO 里那条说的是两回事', () => {
  const po = readPo(PO);
  const files = walk(resolve(UI, 'src/kiosk'), (p) => /\.tsx?$/.test(p) && !p.endsWith('.test.tsx'));
  const cjk = (s: string) => /[\u4e00-\u9fff]/.test(s);
  const hit = new Set<string>();
  for (const p of files) {
    const src = codeOnly(readFileSync(p, 'utf8'));
    for (const m of src.matchAll(/\bt\(\s*'([^'\\]+)'\s*,\s*'([^'\\]*)'\s*\)/g)) {
      const [, key, def] = m;
      const translated = po.get(key);
      if (translated === undefined) continue;
      if (cjk(def) && cjk(translated) && def !== translated) hit.add(`${rel(p)}  ${key}`);
    }
  }
  expect([...hit].sort()).toEqual(PO_OVERRIDES_DEFAULT_BASELINE);
});
