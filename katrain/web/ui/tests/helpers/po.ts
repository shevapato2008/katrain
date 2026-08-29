import { readFileSync } from 'node:fs';

/**
 * `.po` → `{ msgid: msgstr }`,和后端 `/api/translations` 吐的那份**同一形状**。
 *
 * ## 为什么在这儿重写一遍,而不是拿 `.mo`
 *
 * 后端 `server.py:2171` 读的是 gettext 编译出来的 `.mo` 的 `_catalog`。
 * 而 `.mo` **在 .gitignore 里**(`.gitignore:43`)—— 新克隆的工作树里根本没有那个文件,
 * 拿它当测试输入就是「闸的绿取决于本机跑过没跑过 `i18n.py`」。
 * `.po` 是提交进仓的那一份,`.mo` 由它编译而来 ⇒ 判据落在 `.po` 上。
 *
 * 只解析用得上的那几件事:多行续行、转义、跳过 `#~` 的废弃条目、
 * 空 `msgstr` 不进表(gettext 那边也不进 —— 未翻译时回落到 msgid)。
 * `msgctxt` 本仓一条都没有,不处理;真出现了就当普通条目,不额外造键。
 */
export function parsePo(file: string): Record<string, string> {
  const out: Record<string, string> = {};
  const lines = readFileSync(file, 'utf8').split('\n');
  let id: string | null = null;
  let str: string | null = null;
  let target: 'id' | 'str' | null = null;

  const unquote = (raw: string) => raw
    .replace(/\\n/g, '\n').replace(/\\t/g, '\t')
    .replace(/\\"/g, '"').replace(/\\\\/g, '\\');

  const flush = () => {
    if (id !== null && str) out[id] = str;
    id = null; str = null; target = null;
  };

  for (const line of lines) {
    const t = line.trim();
    if (t.startsWith('#~')) { flush(); continue; }     // 废弃条目
    if (t.startsWith('#') || t === '') { if (t === '') flush(); continue; }

    let m = /^msgid\s+"([\s\S]*)"$/.exec(t);
    if (m) { flush(); id = unquote(m[1]); str = ''; target = 'id'; continue; }
    m = /^msgstr\s+"([\s\S]*)"$/.exec(t);
    if (m) { str = unquote(m[1]); target = 'str'; continue; }
    m = /^"([\s\S]*)"$/.exec(t);
    if (m && target) {
      if (target === 'id') id = (id ?? '') + unquote(m[1]);
      else str = (str ?? '') + unquote(m[1]);
      continue;
    }
    flush();
  }
  flush();
  return out;
}
