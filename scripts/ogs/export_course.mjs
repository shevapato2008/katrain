#!/usr/bin/env node
/** Extract the pinned OGS LearningHub as data. Never execute upstream code. */
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const require = createRequire(import.meta.url);
const SOURCE_COMMIT = '1c1c2b82d027f7c307ab25886112cf0a6baf680a';
const GOBAN_COMMIT = 'd7eb38eb4e9e1c48ace12befb98d9f3c821ec2f3';
const LOCALE_VERSION = '5304fd731af8856a16d198d506111d61';
const sha256 = value => createHash('sha256').update(value).digest('hex');

// Sorted keys match Python json.dumps(sort_keys=True, ensure_ascii=False,
// separators=(',', ':')). Screenshot evidence is added independently later.
export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonicalJson(value[k])}`).join(',')}}`;
  return JSON.stringify(value);
}
export function contentHash(bundle) {
  const data = structuredClone(bundle);
  delete data.source?.content_sha256;
  for (const step of data.steps ?? []) delete step.screenshot;
  return sha256(canonicalJson(data));
}

/** OGS raw SGF top-left coordinates or human A1 (bottom-left, skipping I). */
export function decodeMoves(raw, width, height) {
  if (!raw) return [];
  const result = [];
  if (/[a-zA-Z][0-9]/.test(raw)) {
    const tokens = raw.match(/[a-zA-Z][0-9]+|pass|\.\./g) ?? [];
    if (tokens.join('') !== raw) throw new Error(`Unparsed coordinate string: ${raw}`);
    for (const token of tokens) {
      if (token === 'pass' || token === '..') { result.push(null); continue; }
      const x = 'ABCDEFGHJKLMNOPQRSTUVWXYZ'.indexOf(token[0].toUpperCase());
      const y = height - Number(token.slice(1));
      if (x < 0 || x >= width || y < 0 || y >= height) throw new Error(`Out-of-bounds coordinate ${token}`);
      result.push([x, y]);
    }
  } else {
    if (raw.length % 2) throw new Error(`Odd coordinate string: ${raw}`);
    for (let i = 0; i < raw.length; i += 2) {
      const token = raw.slice(i, i + 2);
      if (token === '..') { result.push(null); continue; }
      if (!/^[a-z]{2}$/.test(token)) throw new Error(`Unknown coordinate ${token}`);
      const point = [token.charCodeAt(0) - 97, token.charCodeAt(1) - 97];
      if (point[0] >= width || point[1] >= height) throw new Error(`Out-of-bounds coordinate ${token}`);
      result.push(point);
    }
  }
  return result;
}

export function normalizeStones(initial, width, height) {
  const result = { B: [], W: [] };
  const occupied = new Map();
  for (const [color, key] of [['B', 'black'], ['W', 'white']]) {
    for (const point of decodeMoves(initial[key] ?? '', width, height)) {
      if (!point) throw new Error('A setup stone cannot be pass');
      const coordinate = point.join(',');
      if (occupied.has(coordinate)) {
        if (occupied.get(coordinate) !== color) throw new Error(`Opposite-color collision at ${coordinate}`);
        continue;
      }
      occupied.set(coordinate, color);
      result[color].push(point);
    }
  }
  return result;
}

export function makeMoveTree(correct, wrong, width = 9, height = 9) {
  const root = { point: null, correct: false, wrong: false, children: [] };
  for (const [paths, flag] of [[correct, 'correct'], [wrong, 'wrong']]) {
    for (const raw of paths) {
      let node = root;
      for (const point of decodeMoves(raw, width, height)) {
        let child = node.children.find(c => JSON.stringify(c.point) === JSON.stringify(point));
        if (!child) {
          child = { point, correct: false, wrong: false, children: [] };
          node.children.push(child);
        }
        node = child;
      }
      node[flag] = true;
    }
  }
  return root;
}

function upstreamTree(node) {
  return {
    x: node.point?.[0] ?? -1, y: node.point?.[1] ?? -1,
    branches: node.children.map(upstreamTree),
    ...(node.correct ? { correct_answer: true } : {}),
    ...(node.wrong ? { wrong_answer: true } : {}),
  };
}

function loadTypescript() {
  for (const location of [process.env.OGS_TYPESCRIPT_MODULE, 'typescript', path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../katrain/web/ui/node_modules/typescript')].filter(Boolean)) {
    try { return require(location); } catch { /* Try the next documented dependency location. */ }
  }
  throw new Error('TypeScript parser unavailable. Install existing frontend dependencies, or set OGS_TYPESCRIPT_MODULE to its typescript module path.');
}

class Unsupported extends Error {}

export function exportCourse(sourceRoot, catalogRoot) {
  const ts = loadTypescript();
  const actualCommit = execFileSync('git', ['-C', sourceRoot, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
  if (actualCommit !== SOURCE_COMMIT) throw new Error(`Expected source commit ${SOURCE_COMMIT}; found ${actualCommit}`);
  execFileSync('git', ['-C', sourceRoot, 'diff', '--exit-code', 'HEAD', '--', 'src/views/LearningHub', 'LICENSE'], { stdio: 'pipe' });
  const read = relative => readFileSync(path.join(sourceRoot, relative), 'utf8');
  const parse = (filename, text) => {
    const file = ts.createSourceFile(filename, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    if (file.parseDiagnostics.length) throw new Error(`Invalid TypeScript source: ${filename}`);
    return file;
  };
  const walk = (node, visit) => { visit(node); ts.forEachChild(node, child => walk(child, visit)); };
  const keyName = node => node.text ?? node.getText();
  function literal(node) {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
    if (ts.isNumericLiteral(node)) return Number(node.text);
    if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
    if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
    if (node.kind === ts.SyntaxKind.NullKeyword) return null;
    if (ts.isArrayLiteralExpression(node)) return node.elements.map(literal);
    if (ts.isObjectLiteralExpression(node)) {
      const object = {};
      for (const item of node.properties) {
        if (!ts.isPropertyAssignment(item)) throw new Unsupported('Non-literal object property');
        object[keyName(item.name)] = literal(item.initializer);
      }
      return object;
    }
    throw new Unsupported(`Unsupported expression: ${node.getText().slice(0, 100)}`);
  }
  function message(node) {
    if (ts.isStringLiteral(node)) return { key: node.text, text: node.text };
    if (ts.isCallExpression(node)) {
      const fn = node.expression.getText();
      if (fn === '_' && node.arguments.length === 1) {
        const text = literal(node.arguments[0]); return { key: text, text };
      }
      if (fn === 'pgettext' && node.arguments.length === 2) {
        const [context, text] = node.arguments.map(literal); return { key: `${context}\u0004${text}`, text };
      }
    }
    throw new Unsupported(`Unsupported gettext expression: ${node.getText().slice(0, 100)}`);
  }
  function returnExpression(method) {
    const returns = method?.body?.statements.filter(ts.isReturnStatement) ?? [];
    if (returns.length !== 1) throw new Unsupported('Expected one top-level return');
    return returns[0].expression;
  }
  function method(cls, name) { return cls.members.find(m => ts.isMethodDeclaration(m) && keyName(m.name) === name); }
  function jsxMessage(node) {
    if (ts.isJsxText(node)) return { key: null, text: node.text.replace(/\s+/g, ' ').trim() };
    if (ts.isJsxExpression(node)) {
      if (!node.expression) return { key: null, text: '' };
      return message(node.expression);
    }
    throw new Unsupported(`Unsupported JSX text: ${node.getText().slice(0, 100)}`);
  }
  function extractText(cls) {
    const textMethod = method(cls, 'text');
    const returned = returnExpression(textMethod);
    if (ts.isCallExpression(returned)) return { instruction: message(returned), choices: null };
    const paragraphs = [], labels = [];
    let correct;
    walk(textMethod, node => {
      if (ts.isBinaryExpression(node) && node.left.getText() === 'selectedValue' && node.operatorToken.kind === ts.SyntaxKind.EqualsEqualsEqualsToken) {
        if (correct !== undefined) throw new Unsupported('Multiple correct-choice comparisons');
        correct = literal(node.right);
      }
      if (!ts.isJsxElement(node)) return;
      const tag = node.openingElement.tagName.getText();
      if (tag === 'p') {
        const pieces = node.children.map(jsxMessage).filter(item => item.text);
        if (pieces.length !== 1) throw new Unsupported('Expected a single static instruction message');
        paragraphs.push(pieces[0]);
      }
      if (tag === 'label') {
        let value;
        const pieces = [];
        for (const child of node.children) {
          if (ts.isJsxSelfClosingElement(child) && child.tagName.getText() === 'input') {
            const attrs = child.attributes.properties;
            const type = attrs.find(a => ts.isJsxAttribute(a) && keyName(a.name) === 'type');
            if (literal(type?.initializer) !== 'radio') throw new Unsupported('Only radio choices are supported');
            value = literal(attrs.find(a => ts.isJsxAttribute(a) && keyName(a.name) === 'value')?.initializer);
          } else {
            const piece = jsxMessage(child); if (piece.text) pieces.push(piece);
          }
        }
        if (value === undefined || pieces.length !== 1) throw new Unsupported('Expected static option value and label');
        labels.push({ value, label: pieces[0] });
      }
    });
    if (!paragraphs.length || !labels.length || !labels.some(c => c.value === correct)) throw new Unsupported('Unknown multiple-choice structure');
    return { instruction: paragraphs.length === 1 ? paragraphs[0] : { parts: paragraphs }, choices: labels, correct };
  }

  const catalogs = new Map();
  const other = JSON.parse(readFileSync(path.join(catalogRoot, 'other-language-catalogs.json'), 'utf8'));
  const browser = JSON.parse(readFileSync(path.join(catalogRoot, 'browser-sample-capture.json'), 'utf8'));
  if (other.version !== LOCALE_VERSION || browser.sample.locale_version !== LOCALE_VERSION) throw new Error('Catalog revision mismatch');
  function normalizeCatalog(catalog) {
    return Object.fromEntries(Object.entries(catalog).map(([key, value]) => [key.replaceAll('\\x04', '\u0004').replaceAll('\\u0004', '\u0004'), value]));
  }
  for (const item of [...other.locales, ...browser.locales]) {
    if (item.status !== 200) throw new Error(`Missing catalog ${item.code}`);
    const file = parse(`locale-${item.code}.js`, item.body);
    let catalog;
    walk(file, node => {
      if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken && ts.isElementAccessExpression(node.left) && ts.isObjectLiteralExpression(node.right)) {
        if (node.left.expression.getText().includes('window.ogs_locales') && ts.isStringLiteral(node.left.argumentExpression) && node.left.argumentExpression.text === item.code) catalog = literal(node.right);
      }
    });
    if (!catalog) throw new Error(`Cannot parse catalog ${item.code}`);
    catalogs.set(item.code, normalizeCatalog(catalog));
  }
  catalogs.set('zh-cn', normalizeCatalog(browser.sample.zh_cn));
  const languages = ['en', ...Object.keys(other.languages).filter(c => c !== 'en' && c !== 'auto' && c !== 'debug').sort()];
  if (languages.length !== 32 || languages.some(code => code !== 'en' && !catalogs.has(code))) throw new Error('Expected all 32 source languages');
  const translationStats = Object.fromEntries(languages.map(code => [code, { missing: 0, unchanged: 0 }]));
  const usedMessages = new Map();
  function translate(msg, language) {
    if (msg.parts) {
      const parts = msg.parts.map(part => translate(part, language));
      return { text: parts.map(part => part.text).join('\n\n'), fallback: parts.some(part => part.fallback) };
    }
    if (!msg.key || language === 'en') return { text: msg.text, fallback: false };
    usedMessages.set(msg.key, msg.text);
    const entry = catalogs.get(language)?.[msg.key];
    if (!Array.isArray(entry) || typeof entry[0] !== 'string' || !entry[0]) {
      translationStats[language].missing++; return { text: msg.text, fallback: true };
    }
    if (entry[0] === msg.text) translationStats[language].unchanged++;
    return { text: entry[0], fallback: false };
  }

  const sectionsPath = 'src/views/LearningHub/sections.ts';
  const sectionsText = read(sectionsPath), sectionFile = parse(sectionsPath, sectionsText);
  const imports = new Map();
  let sectionList;
  for (const statement of sectionFile.statements) {
    if (ts.isImportDeclaration(statement) && statement.importClause?.namedBindings && ts.isNamedImports(statement.importClause.namedBindings)) {
      for (const item of statement.importClause.namedBindings.elements) imports.set(item.name.text, statement.moduleSpecifier.text);
    }
    if (ts.isVariableStatement(statement)) for (const declaration of statement.declarationList.declarations) if (declaration.name.getText() === 'sections') sectionList = declaration.initializer;
  }
  if (!ts.isArrayLiteralExpression(sectionList)) throw new Error('Missing registered sections array');
  const bundle = {
    schema_version: 1,
    source: {
      repository: 'https://github.com/online-go/online-go.com', commit: SOURCE_COMMIT,
      goban_commit: GOBAN_COMMIT, locale_version: LOCALE_VERSION,
      license: 'AGPL-3.0-or-later', license_text: read('LICENSE'),
      sections_sha256: sha256(sectionsText),
      ui_translations: {},
    },
    languages, chapters: [], lessons: [], steps: [],
  };
  const uiMessages = { correct: 'Great job!', incorrect: 'Puzzle failed!', next: 'Next', retry: 'Retry', pass: 'Pass', finish: 'Finish' };
  for (const language of languages) bundle.source.ui_translations[language] = Object.fromEntries(Object.entries(uiMessages).map(([id, text]) => [id, translate({ key: text, text }, language).text]));
  const coverage = { counts: {}, kinds: {}, board_sizes: {}, languages: translationStats, unsupported: [], issues: [] };
  function count(target, key) { target[key] = (target[key] ?? 0) + 1; }
  for (const [chapterIndex, section] of sectionList.elements.entries()) {
    if (!ts.isArrayLiteralExpression(section) || section.elements.length !== 2 || !ts.isArrayLiteralExpression(section.elements[1])) throw new Error('Unknown chapter registration');
    const titleMsg = message(section.elements[0]);
    const lessonRefs = section.elements[1].elements;
    const group = imports.get(lessonRefs[0].getText()).split('/')[2];
    const chapter = { id: `ogs-learning:${group}`, number: chapterIndex + 1, title: titleMsg.text, translations: {} };
    for (const language of languages) chapter.translations[language] = { title: translate(titleMsg, language).text };
    bundle.chapters.push(chapter);
    for (const [lessonIndex, ref] of lessonRefs.entries()) {
      const className = ref.getText();
      const relative = path.posix.normalize(path.posix.join('src/views/LearningHub', `${imports.get(className)}.tsx`));
      const text = read(relative), file = parse(relative, text);
      const classes = new Map(file.statements.filter(ts.isClassDeclaration).map(c => [c.name.text, c]));
      const lessonClass = classes.get(className);
      const route = literal(returnExpression(method(lessonClass, 'section')));
      const title = message(returnExpression(method(lessonClass, 'title')));
      const subtext = message(returnExpression(method(lessonClass, 'subtext')));
      const pages = returnExpression(method(lessonClass, 'pages'));
      if (!ts.isArrayLiteralExpression(pages)) throw new Error(`Unknown pages for ${className}`);
      const lesson = {
        id: route, chapter_id: chapter.id, order: lessonIndex + 1,
        course_code: `${chapterIndex + 1}.${lessonIndex + 1}`, route,
        title: title.text, step_count: pages.elements.length, first_page: bundle.steps.length + 1, translations: {},
      };
      for (const language of languages) lesson.translations[language] = { title: translate(title, language).text, subtext: translate(subtext, language).text };
      bundle.lessons.push(lesson);
      for (const [pageIndex, pageRef] of pages.elements.entries()) {
        const pageClass = classes.get(pageRef.getText());
        const step = {
          source_id: `ogs-learning:${route}:${pageIndex + 1}`, lesson_id: route, step: pageIndex + 1,
          page: bundle.steps.length + 1,
          source_url: `https://online-go.com/learn-to-play-go/${encodeURIComponent(route)}/${pageIndex}`,
          size: 9, initial_player: 'B', stones: { B: [], W: [] }, letters: {}, shapes: {}, viewport: null,
          exercise: { kind: 'unsupported' }, translations: {},
          raw_source: { file: relative, lesson_class: className, page_class: pageRef.getText(), source_step_index: pageIndex, sha256: sha256(text) },
          issues: [],
        };
        let parsedText;
        try {
          parsedText = extractText(pageClass);
          const configExpression = returnExpression(method(pageClass, 'config'));
          step.raw_source.config_source = configExpression.getText(file);
          if (!ts.isObjectLiteralExpression(configExpression)) throw new Unsupported('Non-object config');
          const config = {};
          let tree;
          for (const prop of configExpression.properties) {
            if (!ts.isPropertyAssignment(prop)) throw new Unsupported('Non-literal config property');
            const key = keyName(prop.name);
            if (key === 'move_tree') {
              const call = prop.initializer;
              if (!ts.isCallExpression(call) || call.expression.getText() !== 'this.makePuzzleMoveTree' || ![2, 4].includes(call.arguments.length)) throw new Unsupported('Unknown move-tree constructor');
              const [correct, wrong, width = 9, height = 9] = call.arguments.map(literal);
              tree = makeMoveTree(correct, wrong, width, height);
              Object.assign(step.raw_source, { correct_paths: correct, wrong_paths: wrong, tree_width: width, tree_height: height });
              config.move_tree = upstreamTree(tree);
            } else config[key] = literal(prop.initializer);
          }
          step.raw_source.config = config;
          const allowed = new Set(['width', 'height', 'mode', 'phase', 'initial_player', 'initial_state', 'marks', 'bounds', 'move_tree']);
          if (Object.keys(config).some(key => !allowed.has(key))) throw new Unsupported('Unknown configuration keys');
          const width = config.width ?? 9, height = config.height ?? 9;
          if (width !== height || ![9, 13, 19].includes(width)) throw new Unsupported('Unknown board dimensions');
          step.size = width;
          if (!['black', 'white'].includes(config.initial_player ?? 'black')) throw new Unsupported('Unknown initial player');
          step.initial_player = config.initial_player === 'white' ? 'W' : 'B';
          step.stones = normalizeStones(config.initial_state, width, height);
          const rawCount = ['black', 'white'].reduce((sum, c) => sum + decodeMoves(config.initial_state[c] ?? '', width, height).length, 0);
          if (rawCount !== step.stones.B.length + step.stones.W.length) step.issues.push('duplicate_same_color_setup_deduplicated');
          for (const [mark, raw] of Object.entries(config.marks ?? {})) {
            const target = ['cross', 'triangle', 'square'].includes(mark) ? step.shapes : step.letters;
            if (target === step.letters && !/^[A-Za-z0-9]{1,2}$/.test(mark)) throw new Unsupported(`Unknown mark ${mark}`);
            for (const point of decodeMoves(raw, width, height)) {
              if (!point) throw new Unsupported('Pass mark');
              target[point.join(',')] = mark;
            }
          }
          if (config.bounds) {
            const { left, top, right, bottom } = config.bounds;
            step.viewport = { col: left, row: top, cols: right - left + 1, rows: bottom - top + 1 };
          }
          if (route === 'ending-the-game') {
            const kind = ['pass', 'remove', 'finish'][pageIndex];
            if (!kind) throw new Unsupported('Unknown ending step');
            step.exercise = { kind };
            if (kind === 'remove') {
              const removalMethod = method(pageClass, 'onStoneRemoval');
              let target;
              walk(removalMethod, node => {
                if (ts.isBinaryExpression(node) && node.left.getText() === 'stone_removal_string' && node.operatorToken.kind === ts.SyntaxKind.EqualsEqualsEqualsToken) target = literal(node.right);
              });
              if (target !== 'fafbgbhb') throw new Unsupported('Unknown removal condition');
              step.exercise.remove_targets = decodeMoves(target, width, height);
              step.raw_source.removal_string = target;
            } else {
              const button = method(pageClass, 'button');
              step.raw_source.button_source = button.getText(file);
              let actionLabel;
              walk(button, node => { if (ts.isJsxExpression(node) && node.expression && ts.isCallExpression(node.expression)) actionLabel = message(node.expression); });
              step.raw_source.action_label_key = actionLabel.key;
            }
            step.raw_source.completion_source = method(pageClass, 'complete').getText(file);
          } else if (parsedText.choices) {
            if (tree || config.phase !== 'finished') throw new Unsupported('Unknown multiple-choice mode');
            step.exercise = { kind: 'choice', choices: parsedText.choices.map(c => ({ value: c.value, label_key: c.label.key ?? c.label.text })), correct_choice: parsedText.correct };
          } else {
            if (!tree || config.mode !== 'puzzle') throw new Unsupported('Unknown puzzle mode');
            step.exercise = { kind: 'puzzle', tree };
            if (tree.wrong) step.issues.push('root_wrong_answer');
          }
        } catch (error) {
          if (!(error instanceof Unsupported)) throw new Error(`${step.source_id}: ${error.message}`, { cause: error });
          step.exercise = { kind: 'unsupported' };
          step.issues.push(error.message);
          coverage.unsupported.push({ source_id: step.source_id, reason: error.message });
        }
        for (const language of languages) {
          const translatedTitle = translate(title, language);
          const instruction = parsedText ? translate(parsedText.instruction, language) : { text: '', fallback: true };
          const translated = { title: translatedTitle.text, instruction: instruction.text, fallback: translatedTitle.fallback || instruction.fallback };
          if (parsedText?.choices) {
            translated.choices = {};
            for (const choice of parsedText.choices) {
              const label = translate(choice.label, language);
              translated.choices[choice.value] = label.text; translated.fallback ||= label.fallback;
            }
          }
          step.translations[language] = translated;
        }
        const zh = step.translations['zh-cn'].instruction;
        const en = step.translations.en.instruction;
        if ((/Black to play/i.test(en) && /白先/.test(zh)) || (/White to play/i.test(en) && /黑先/.test(zh))) step.issues.push('zh_cn_initial_player_translation_mismatch');
        for (const issue of step.issues) coverage.issues.push({ source_id: step.source_id, issue });
        count(coverage.kinds, step.exercise.kind); count(coverage.board_sizes, step.size);
        bundle.steps.push(step);
      }
    }
  }
  if (bundle.chapters.length !== 7 || bundle.lessons.length !== 248 || bundle.steps.length !== 3551) throw new Error('Pinned source registration counts changed');
  bundle.source.content_sha256 = contentHash(bundle);
  coverage.counts = { chapters: bundle.chapters.length, lessons: bundle.lessons.length, steps: bundle.steps.length, languages: languages.length, message_keys: usedMessages.size };
  coverage.content_sha256 = bundle.source.content_sha256;
  coverage.source_commit = SOURCE_COMMIT;
  return { bundle, coverage };
}

function main() {
  const options = {};
  for (let i = 2; i < process.argv.length; i += 2) {
    const key = process.argv[i];
    if (!['--source-root', '--catalog-root', '--research-root', '--output', '--coverage'].includes(key) || !process.argv[i + 1]) throw new Error(`Unknown or missing option: ${key}`);
    options[key] = process.argv[i + 1];
  }
  const sourceRoot = options['--source-root'];
  const catalogRoot = options['--catalog-root'] ?? options['--research-root'];
  const output = options['--output'];
  if (!sourceRoot || !catalogRoot || !output) throw new Error('Usage: node export_course.mjs --source-root PATH --catalog-root PATH --output PATH');
  const { bundle, coverage } = exportCourse(path.resolve(sourceRoot), path.resolve(catalogRoot));
  mkdirSync(path.dirname(path.resolve(output)), { recursive: true });
  writeFileSync(output, `${JSON.stringify(bundle, null, 2)}\n`);
  writeFileSync(options['--coverage'] ?? path.join(path.dirname(output), 'coverage.json'), `${JSON.stringify(coverage, null, 2)}\n`);
  process.stdout.write(`${JSON.stringify({ ...coverage.counts, kinds: coverage.kinds, unsupported: coverage.unsupported.length, content_sha256: coverage.content_sha256 })}\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  try { main(); } catch (error) { process.stderr.write(`${error.message}\n`); process.exitCode = 1; }
}
