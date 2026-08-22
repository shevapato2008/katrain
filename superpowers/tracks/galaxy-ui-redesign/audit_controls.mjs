/**
 * 控件账本 —— 全站风格统一的「不许丢按钮 / 不许多出空按钮」闸。
 *
 * 用 TypeScript 编译器 API 静态扫 TSX，把每个页面里**可点的东西**逐个记下来：
 * 可及名（aria-label → title → label → 子文本）、控件类型、行号、有没有挂 handler。
 *
 * 为什么是静态不是跑浏览器：迁移是逐页改同一个文件，需要的判据是
 * 「同一文件改前 vs 改后」的集合差，跟后端有没有数据无关；跑浏览器那一关
 * 留给每页的四图对比和承重实测。
 *
 * 用法：
 *   node audit_controls.mjs <file...>            # 当前工作区
 *   node audit_controls.mjs --rev HEAD <file...> # 某个 commit 的版本
 *   node audit_controls.mjs --json ...           # 机器可读
 *   node audit_controls.mjs --diff <revA> <file...>  # revA vs 工作区，只打差异
 */
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';

const require = createRequire(path.resolve('katrain/web/ui/package.json'));
const ts = require('typescript');

/* MUI + 原生里「用户能点/能改」的东西。Box/Typography 这类只有在带 onClick 时
   才算控件，单独列在 IMPLICIT 里按 handler 判定。 */
const CONTROL_TAGS = new Set([
  /* 项目自己的控件包装件。登记判据：**组件自己渲染一个真控件、并把可及名透传下去**
     （`ToolGridButton` 渲染 ButtonBase + aria-label）。不登记的话账本看不见它，
     于是「把四个 IconButton 换成工具格键」会报成丢失 4 —— 闸量错了对象。
     新增这类包装件必须同时登记到这里；忘了登记会被下面那条「未登记的疑似包装件」抓到。 */
  'ButtonBase', 'ToolGridButton',
  'Button', 'IconButton', 'LoadingButton', 'Fab', 'ToggleButton', 'Switch', 'Checkbox',
  'Radio', 'Slider', 'Tab', 'MenuItem', 'TextField', 'Select', 'NativeSelect', 'Autocomplete',
  'Link', 'ListItemButton', 'CardActionArea', 'Chip', 'Rating', 'Pagination', 'PaginationItem',
  'button', 'input', 'select', 'textarea', 'a',
]);
const IMPLICIT_TAGS = new Set(['Box', 'Paper', 'Card', 'Stack', 'Typography', 'div', 'span', 'li', 'tr']);
const HANDLER_ATTRS = ['onClick', 'onChange', 'onSubmit', 'onInput', 'onMouseDown', 'onKeyDown', 'onToggle', 'onDelete'];
/* Chip 只有可点/可删时才算控件，纯状态标签不进账本 */
const CONDITIONAL_TAGS = new Set(['Chip', 'Typography', 'Box', 'Paper', 'Card', 'Stack', 'div', 'span', 'li', 'tr']);

function attr(node, name) {
  for (const p of node.attributes.properties) {
    if (ts.isJsxAttribute(p) && p.name.getText() === name) return p;
  }
  return null;
}

/** 从属性值里挖出一个人能读的名字：字面量、t('k','中文') 的第二个参数、模板串 */
function textOf(init) {
  if (!init) return null;
  if (ts.isStringLiteral(init)) return init.text;
  if (ts.isJsxExpression(init) && init.expression) return textOf(init.expression);
  if (ts.isNoSubstitutionTemplateLiteral(init)) return init.text;
  if (ts.isTemplateExpression(init)) {
    /* `${t('tsumego:undo')} (U)` 要解成「撤销 (U)」，不能只留个 ${…} */
    return init.head.text + init.templateSpans
      .map(s => (textOf(s.expression) ?? '${…}') + s.literal.text).join('');
  }
  if (ts.isCallExpression(init)) {
    const fn = init.expression.getText();
    if (fn === 't' || fn.endsWith('.t')) {
      const fallback = init.arguments[1];
      if (fallback && ts.isStringLiteral(fallback)) return fallback.text;
      const key = init.arguments[0];
      if (key && ts.isStringLiteral(key)) return 't:' + key.text;
    }
    return null;
  }
  if (ts.isConditionalExpression(init)) {
    const a = textOf(init.whenTrue), b = textOf(init.whenFalse);
    if (a && b) return a + ' | ' + b;
    return a || b;
  }
  return null;
}

/** 往上找包着它的 <Tooltip title=…>：MUI 里图标键的可及名常常只挂在 Tooltip 上 */
function tooltipText(node) {
  let p = node.parent;
  for (let i = 0; p && i < 4; i++, p = p.parent) {
    const open = ts.isJsxElement(p) ? p.openingElement : null;
    if (open && open.tagName.getText() === 'Tooltip') return textOf(attr(open, 'title')?.initializer);
  }
  return null;
}

/** 子节点里第一个 <XxxIcon /> —— 没有任何文字时用它当身份 */
function iconChild(node) {
  const kids = ts.isJsxElement(node.parent) ? node.parent.children : [];
  for (const c of kids) {
    const tag = ts.isJsxSelfClosingElement(c) ? c.tagName.getText()
      : ts.isJsxElement(c) ? c.openingElement.tagName.getText() : null;
    if (tag && /Icon$/.test(tag)) return 'icon:' + tag.replace(/Icon$/, '');
  }
  return null;
}

/** Switch/Checkbox 的可及名藏在 `slotProps={{ input: { 'aria-label': … } }}`（MUI v7）
 *  或旧的 `inputProps={{ 'aria-label': … }}` 里。**只有前者在 v7 里真的到得了那个 input**
 *  —— 实测 `inputProps` 写法下浏览器读到的 aria-label 是 null，账本却报出了名字。
 *  所以两种都读，但读到旧写法时标注出来，免得账本比浏览器乐观。 */
function objLiteralProp(obj, key) {
  if (!obj || !ts.isObjectLiteralExpression(obj)) return null;
  for (const prop of obj.properties) {
    if (!ts.isPropertyAssignment(prop)) continue;
    const name = ts.isStringLiteral(prop.name) || ts.isIdentifier(prop.name) ? prop.name.text : null;
    if (name === key) return prop.initializer;
  }
  return null;
}

function inputPropsLabel(node) {
  const slotInit = attr(node, 'slotProps')?.initializer;
  if (slotInit && ts.isJsxExpression(slotInit) && slotInit.expression) {
    const input = objLiteralProp(slotInit.expression, 'input');
    const label = input && ts.isObjectLiteralExpression(input) ? objLiteralProp(input, 'aria-label') : null;
    if (label) return textOf(label);
  }
  const legacy = attr(node, 'inputProps')?.initializer;
  if (legacy && ts.isJsxExpression(legacy) && legacy.expression) {
    const label = objLiteralProp(legacy.expression, 'aria-label');
    if (label) {
      const t = textOf(label);
      return t ? t + ' [inputProps: MUI v7 下到不了 input]' : null;
    }
  }
  return null;
}

/** 子节点里的第一段人能读的文字 */
function childText(node) {
  const parent = node.parent;
  if (!parent || !ts.isJsxElement(parent)) return null;
  for (const c of parent.children) {
    if (ts.isJsxText(c)) {
      const t = c.text.trim();
      if (t) return t;
    } else if (ts.isJsxExpression(c) && c.expression) {
      const t = textOf(c.expression);
      if (t) return t;
    }
  }
  return null;
}

function isNoop(p) {
  const init = p.initializer;
  if (!init || !ts.isJsxExpression(init) || !init.expression) return false;
  const e = init.expression;
  if (e.kind === ts.SyntaxKind.UndefinedKeyword) return true;
  if (ts.isArrowFunction(e)) {
    const b = e.body;
    if (ts.isBlock(b) && b.statements.length === 0) return true;
    if (b.kind === ts.SyntaxKind.NullKeyword) return true;
    if (ts.isIdentifier(b) && b.text === 'undefined') return true;
  }
  return false;
}

/** 大写开头、不在任何已知集合里、却挂了 onClick 的标签 —— 多半是个控件包装件，
 *  而账本看不见它。不判失败（有些确实只是可点的展示块），但必须说出来：
 *  闸看不见的东西等于没有闸。 */
export const unregisteredWrappers = new Map();

export function scan(source, fileName) {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const out = [];
  const visit = (node) => {
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      const tag = node.tagName.getText();
      const handlers = HANDLER_ATTRS.map(h => attr(node, h)).filter(Boolean);
      const hasHref = !!attr(node, 'href') || !!attr(node, 'to');
      const isControl = CONTROL_TAGS.has(tag) && !CONDITIONAL_TAGS.has(tag);
      const isImplicit = CONDITIONAL_TAGS.has(tag) && (handlers.length > 0 || attr(node, 'role'));
      /* MenuItem / Tab / ToggleButton / Radio 的 handler 挂在父容器上
         （Select.onChange / Tabs.onChange / ToggleButtonGroup.onChange），
         不认这层继承就会把一堆正常选项误判成空按钮 —— 会哭狼的闸没人看。 */
      const GROUPED = { MenuItem: ['Select', 'TextField', 'Menu', 'Autocomplete'], Tab: ['Tabs'],
        ToggleButton: ['ToggleButtonGroup'], Radio: ['RadioGroup'], FormControlLabel: ['RadioGroup', 'FormGroup'] };
      let inherited = false;
      {
        let a = node.parent;
        for (let i = 0; a && i < 10; i++, a = a.parent) {
          const open = ts.isJsxElement(a) ? a.openingElement : null;
          if (!open) continue;
          const ptag = open.tagName.getText();
          const pHas = HANDLER_ATTRS.some(h => attr(open, h));
          if (!pHas) continue;
          /* ① 选项类：handler 挂在 Select / Tabs / ToggleButtonGroup 上 */
          if (GROUPED[tag] && GROUPED[tag].includes(ptag)) { inherited = true; break; }
          /* ② 整块可点：外面那层 Box/行 挂了 onClick，里面的图标键只是装饰 */
          if (i <= 3 && CONDITIONAL_TAGS.has(ptag)) { inherited = true; break; }
        }
      }
      /* component="label" 的按钮包着隐藏 <input type=file>，点它就是点 input */
      const asLabel = textOf(attr(node, 'component')?.initializer) === 'label';
      /* disabled 的骨架占位按钮不是空按钮 */
      const isDisabled = !!attr(node, 'disabled');
      if (!isControl && !isImplicit && /^[A-Z]/.test(tag) && !CONTROL_TAGS.has(tag)
          && !IMPLICIT_TAGS.has(tag) && attr(node, 'onClick')) {
        const seen = unregisteredWrappers.get(tag) || new Set();
        seen.add(fileName);
        unregisteredWrappers.set(tag, seen);
      }
      if (isControl || isImplicit) {
        const name =
          textOf(attr(node, 'aria-label')?.initializer) ??
          /* 包装件把 ariaLabel 透传成 aria-label；MUI Switch/Checkbox 把可及名
             塞在 inputProps 里。两处都是真的可及名，不认就只能报 «Switch»。 */
          textOf(attr(node, 'ariaLabel')?.initializer) ??
          inputPropsLabel(node) ??
          textOf(attr(node, 'title')?.initializer) ??
          textOf(attr(node, 'label')?.initializer) ??
          textOf(attr(node, 'placeholder')?.initializer) ??
          childText(node) ??
          tooltipText(node) ??
          iconChild(node) ??
          null;
        const dead = handlers.length === 0 && !hasHref && !inherited && !asLabel && !isDisabled
          ? (['TextField', 'Slider', 'Switch', 'Checkbox', 'Radio', 'Select', 'input', 'textarea', 'select'].includes(tag)
            ? 'uncontrolled' : 'no-handler')
          : (handlers.some(isNoop) ? 'noop' : 'ok');
        out.push({
          tag,
          name: name || `«${tag}»`,
          named: !!name,
          line: sf.getLineAndCharacterOfPosition(node.getStart()).line + 1,
          handler: dead,
        });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  return out;
}

/* ── CLI ───────────────────────────────────────────────────────── */
const argv = process.argv.slice(2);
const asJson = argv.includes('--json');
let rev = null, diffRev = null;
const files = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--json') continue;
  else if (argv[i] === '--rev') rev = argv[++i];
  else if (argv[i] === '--diff') diffRev = argv[++i];
  else files.push(argv[i]);
}
const read = (f, atRev) => atRev
  ? execFileSync('git', ['show', `${atRev}:${f}`], { encoding: 'utf8', maxBuffer: 1 << 26 })
  : fs.readFileSync(f, 'utf8');

/* 身份认**可及名**，不认 MUI 标签。全站风格统一这件事本身就是在换实现：
   把 IconButton 换成工具格键、把 Button 换成 ButtonBase 包装件，如果 key 里带上标签，
   每一次重做都报成「丢失 1 / 新增 1」，真的丢了一个反而淹在噪声里。
   人看得见的身份是那个可及名，闸就该断言那个。改的是判据不是页面。 */
const key = (c) => c.name;

if (diffRev) {
  let lost = 0, added = 0, dead = 0;
  for (const f of files) {
    let before;
    try { before = scan(read(f, diffRev), f); } catch { before = []; }
    /* 文件被删掉 ⇒ 现状是 0 个控件，里面的东西**全部**报成丢失。
       以前这里直接让 ENOENT 冒出去把进程打死 —— 而删文件恰恰是控件最容易丢的一步，
       闸在最该说话的时候崩掉了。 */
    let after;
    try { after = scan(read(f, null), f); }
    catch (e) { if (e.code === 'ENOENT') after = []; else throw e; }
    const bMap = new Map(); before.forEach(c => bMap.set(key(c), (bMap.get(key(c)) || 0) + 1));
    const aMap = new Map(); after.forEach(c => aMap.set(key(c), (aMap.get(key(c)) || 0) + 1));
    const gone = [...bMap].filter(([k, n]) => (aMap.get(k) || 0) < n);
    const neu = [...aMap].filter(([k, n]) => (bMap.get(k) || 0) < n);
    const bad = after.filter(c => c.handler === 'noop' || (c.handler === 'no-handler' && c.tag !== 'a'));
    lost += gone.length; added += neu.length; dead += bad.length;
    if (gone.length || neu.length || bad.length) {
      const tagsOf = (list, k) => [...new Set(list.filter(c => key(c) === k).map(c => c.tag))].join('/');
      console.log(`\n── ${f}  (${before.length} → ${after.length})`);
      gone.forEach(([k, n]) => console.log(`   丢失  ${k}  [${tagsOf(before, k)}]  ×${n - (aMap.get(k) || 0)}`));
      neu.forEach(([k, n]) => console.log(`   新增  ${k}  [${tagsOf(after, k)}]  ×${n - (bMap.get(k) || 0)}`));
      bad.forEach(c => console.log(`   空键  ${c.tag} "${c.name}" :${c.line}  (${c.handler})`));
    }
  }
  console.log(`\n合计：丢失 ${lost} 类 / 新增 ${added} 类 / 空按钮 ${dead} 个`);
  reportUnregistered();
  process.exit(lost || dead ? 1 : 0);
}

function reportUnregistered() {
  if (!unregisteredWrappers.size) return;
  console.log(`\n注意：以下标签挂了 onClick 但不在账本认得的集合里，账本看不见它们的调用点。`);
  console.log(`若它们渲染的是真控件，登记到 CONTROL_TAGS；若只是可点的展示块，可以不管。`);
  for (const [tag, fileSet] of [...unregisteredWrappers].sort()) {
    console.log(`   ${tag}  ←  ${[...fileSet].join(', ')}`);
  }
}

const report = {};
for (const f of files) report[f] = scan(read(f, rev), f);
if (asJson) {
  console.log(JSON.stringify(report, null, 1));
} else {
  for (const [f, list] of Object.entries(report)) {
    console.log(`\n══ ${f}  —— ${list.length} 个控件`);
    for (const c of list) {
      const flag = c.handler === 'ok' ? '  ' : c.handler === 'uncontrolled' ? '~ ' : '! ';
      console.log(`${flag}${String(c.line).padStart(4)}  ${c.tag.padEnd(16)} ${c.name}${c.handler === 'ok' ? '' : '   [' + c.handler + ']'}`);
    }
  }
  reportUnregistered();
}
