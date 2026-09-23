import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * kiosk **不许**调 `API.newGame`。
 *
 * ## 这条闸守的是另一条闸的完整性
 *
 * 让子局的 `komi` 必须是 0(白方的补偿由 KataGo 按规则自动加,再写一遍就补两遍)。
 * 前端在 `utils/setupOptions.ts` 的 `resolveGameTerms` 保证,后端在
 * `katrain/web/server.py` 的 `_kiosk_game_terms` 再兜一道。
 *
 * **但那道兜底只长在 kiosk 那三个 mode 的分支上**(`free` / `ranked` / `pvp_local`,
 * 走 `POST /api/game/setup`)。`API.newGame`(`src/api.ts:359`)打的是另一个端点
 * `POST /api/new-game`,那里 `request.handicap` / `request.komi` **原样透传**给
 * `_do_new_game`(`server.py:1202-1208`)—— 绕开兜底。
 *
 * 兜底**故意**不加在 `_do_new_game` 上:那个函数同时服务 galaxy 的 `NewGameDialog`
 * (`src/components/NewGameDialog.tsx:285` 和 `:305` 是两个互不耦合的自由数字框)
 * 和 `/api/new-game` 自己。在那一层归零 = 把用户亲手输的 6.5 悄悄改成 0,
 * 方向和要修的毛病一模一样,只是反过来。
 *
 * ⇒ 「兜底是完整的」这句话,前提是 **kiosk 不走那条路**。今天成立(零调用者),
 * 而这个前提**没有任何地方写着**。哪天「再来一局」之类的功能图省事用了 `API.newGame`,
 * 让子局的 komi 兜底会在那一条路上**静默失效 —— 而且失效的样子和正常的一模一样**。
 * 这条闸就是把那个前提钉下来。
 *
 * 红了怎么办:不是把这条闸加白名单,是**让新的调用点走 `API.gameSetup`**
 * (那条路有兜底),或者把兜底一起挪到新端点上。
 */

const KIOSK = join(dirname(fileURLToPath(import.meta.url)), '..');

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      if (name === '__tests__' || name === 'node_modules') continue;
      sourceFiles(full, out);
    } else if (/\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name)) {
      out.push(full);
    }
  }
  return out;
}

/** 去掉注释 —— 一条闸误报一次就会长出白名单,而注释里提到它不是违规。 */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');
}

describe('kiosk 不许绕过 `_kiosk_game_terms`', () => {
  it('闸自己先能取到操作数 —— 取不到就是闸瞎了,不是被测的东西对了', () => {
    const files = sourceFiles(KIOSK);
    expect(files.length, 'kiosk 源码一个都没扫到,这条闸的路径写错了').toBeGreaterThan(50);
    // 确认扫到的确实是 kiosk 的源码,而不是别处
    expect(files.some((f) => f.endsWith('pages/AiSetupPage.tsx'))).toBe(true);
  });

  it('`src/kiosk/**` 里没有任何 `API.newGame` 调用', () => {
    const offenders = sourceFiles(KIOSK)
      .filter((f) => /\bAPI\s*\.\s*newGame\s*\(/.test(stripComments(readFileSync(f, 'utf8'))))
      .map((f) => relative(KIOSK, f));
    expect(offenders, [
      `这些文件调了 API.newGame:${offenders.join(', ')}`,
      '那条路打 POST /api/new-game,handicap/komi 原样透传,',
      '绕开 server.py 的 _kiosk_game_terms —— 让子局的 komi 兜底在那条路上静默失效。',
      '改走 API.gameSetup,或者把兜底一起挪到新端点上。别给这条闸加白名单。',
    ].join('\n')).toEqual([]);
  });
});
