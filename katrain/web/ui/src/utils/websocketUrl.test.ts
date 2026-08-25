/**
 * 对局 WebSocket 必须带凭据 —— 这是 2026-08-25 那次「自由对弈无法落子」的根因。
 *
 * 现场：`/ws/{session_id}` 的鉴权在 `c751e8dd`（2026-08-04）从「只在 strict box
 * 模式下检查」改成**无条件**检查，而前端三个对局调用点
 * （useGameSession / useSessionBase / ZenModeApp）从来不带凭据。于是在任何
 * 非 127.0.0.1 的部署上，服务端一律 `close(1008, "Invalid token")`。
 * 实测（测试机 home-ubuntu，原始 close 帧）：
 *   不带 token          → CLOSE code=1008 reason='Invalid token'
 *   带一个有效 token    → CLOSE code=1008 reason='Session not found'   ← 鉴权已通过
 * 后者只是因为探针用了不存在的 session id —— 也就是说**唯一的拦路点就是缺凭据**。
 *
 * 用户看到的是「落不了子」：AI 在后台线程走子，它那一手只经 WS 广播推送
 * （`interface.py::_do_ai_move_and_broadcast` → `update_state`），HTTP 落子响应里
 * 没有。WS 断 ⇒ 棋盘永远停在人类那一手 ⇒ 用户去点 AI 已经占了的位置 ⇒ 后端
 * `Illegal Move: Space occupied`（而且 `_do_play` 吞掉异常、端点照样返回 200）。
 * 生产日志里那三次间隔 5 秒、3 秒的连续失败，就是人在反复点同一个点。
 *
 * 下面第二、三组是**闸**不是单元测试：把任何一个调用点改回手搓 URL，或者把对局
 * WS 的 token 参数去掉，它们必须变红。两组都做过变异验证（见各自 docstring）。
 */
import { describe, it, expect, vi } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { websocketUrl, WS_POLICY_VIOLATION } from './websocketUrl';

const SRC = join(__dirname, '..');

function sourceFiles(): string[] {
    const out: string[] = [];
    const walk = (dir: string) => {
        for (const name of readdirSync(dir)) {
            if (name === 'node_modules' || name === 'dist') continue;
            const full = join(dir, name);
            if (statSync(full).isDirectory()) {
                walk(full);
            } else if (/\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name)) {
                out.push(full);
            }
        }
    };
    walk(SRC);
    return out;
}

describe('websocketUrl', () => {
    it('token 在时拼成 query 参数', () => {
        expect(websocketUrl('/ws/abc', 'tok123')).toBe('ws://localhost:3000/ws/abc?token=tok123');
    });

    it('token 做 URL 编码 —— JWT 里的 +/= 不编码会被服务端读成别的值', () => {
        expect(websocketUrl('/ws/abc', 'a+b/c=d')).toBe('ws://localhost:3000/ws/abc?token=a%2Bb%2Fc%3Dd');
    });

    it('token 缺席时不拼空参数 —— 盒子上靠 cookie 认证', () => {
        expect(websocketUrl('/ws/vision')).toBe('ws://localhost:3000/ws/vision');
        expect(websocketUrl('/ws/vision', null)).toBe('ws://localhost:3000/ws/vision');
        expect(websocketUrl('/ws/vision', '')).toBe('ws://localhost:3000/ws/vision');
    });

    it('https 页面用 wss —— 线上两个环境都是 https，走的正是这一支', () => {
        vi.stubGlobal('location', { protocol: 'https:', host: 'go.sailorvoyage.top' });
        try {
            expect(websocketUrl('/ws/abc', 't')).toBe('wss://go.sailorvoyage.top/ws/abc?token=t');
        } finally {
            vi.unstubAllGlobals();
        }
    });

    it('1008 就是服务端拒绝凭据时用的那个 code', () => {
        expect(WS_POLICY_VIOLATION).toBe(1008);
    });
});

describe('闸：不许再手搓 WebSocket URL', () => {
    /**
     * 变异验证（已真跑）：把 useGameSession.ts 的 `websocketUrl(...)` 改回
     * `` `${protocol}//${window.location.host}/ws/${sessionId}` ``
     * ⇒ 本组两条 + 下一组的「一个都不少」共 3 条转红。
     *
     * 守的是漂移本身 —— 出事前同一条规则散在 5 处（2 个大厅带了 token、
     * 3 个对局没带），谁也不知道另外几处长什么样。
     */
    it('每个 new WebSocket() 的参数都来自 websocketUrl()', () => {
        const offenders: string[] = [];
        for (const file of sourceFiles()) {
            const text = readFileSync(file, 'utf8');
            for (const m of text.matchAll(/new WebSocket\(\s*([^)]*?)\s*\)/g)) {
                const arg = m[1];
                if (arg.includes('websocketUrl(')) continue;
                // `const wsUrl = websocketUrl(...)` 之后 `new WebSocket(wsUrl)` 也算合规
                const ident = arg.trim();
                if (/^[A-Za-z_$][\w$]*$/.test(ident)) {
                    const assigned = new RegExp(`(?:const|let|var)\\s+${ident}\\s*=\\s*websocketUrl\\(`);
                    if (assigned.test(text)) continue;
                }
                offenders.push(`${relative(SRC, file)}: new WebSocket(${arg})`);
            }
        }
        expect(offenders, '这些地方绕过了 websocketUrl()，凭据规则会再次漂移').toEqual([]);
    });

    it('协议三元式只许出现在 helper 里', () => {
        const offenders = sourceFiles()
            .filter((f) => relative(SRC, f) !== join('utils', 'websocketUrl.ts'))
            .filter((f) => /'wss:'\s*:\s*'ws:'/.test(readFileSync(f, 'utf8')))
            .map((f) => relative(SRC, f));
        expect(offenders, '手搓 ws/wss 协议 = 又一份会漂移的副本').toEqual([]);
    });
});

describe('闸：对局 WebSocket 必须带凭据', () => {
    /**
     * 变异验证（已真跑）：把三个对局调用点里任意一个的第二个参数 `token` 删掉
     * ⇒ 本组两条转红。
     *
     * 与上一组不同 —— 上一组只管「有没有走 helper」，这组管「走了 helper 但没给
     * 凭据」。出事那版正是后一种形状：URL 拼得好好的，就是不带 token。
     * 判别口径：第一个参数里带 `/ws/${`（插值出 session id 的会话路径）就必须有
     * 第二个参数。`/ws/vision` 与 `/ws/lobby` 是字面量路径，不受此条约束
     * （vision 服务端不鉴权，lobby 一直带着 token）。
     */
    it('凡是 /ws/${...} 这种会话路径，websocketUrl 都要收到 token', () => {
        const offenders: string[] = [];
        for (const file of sourceFiles()) {
            const text = readFileSync(file, 'utf8');
            for (const m of text.matchAll(/websocketUrl\(\s*(`[^`]*`|'[^']*')\s*(,)?/g)) {
                const [, pathArg, comma] = m;
                if (!pathArg.includes('/ws/${')) continue;  // 只管会话路径
                if (!comma) offenders.push(`${relative(SRC, file)}: websocketUrl(${pathArg}) 没带凭据`);
            }
        }
        expect(offenders, '对局 WS 不带凭据 ⇒ 服务端 close(1008) ⇒ AI 的手推不过来').toEqual([]);
    });

    it('三个对局调用点一个都不少', () => {
        // 逐项断言对「整项没了」免疫，所以这里正查一遍：这三个文件必须都还在通过
        // websocketUrl 连对局 WS 且带着凭据。有人把某个调用点整个删掉/改名要看得见。
        for (const rel of ['hooks/useGameSession.ts', 'hooks/useSessionBase.ts', 'ZenModeApp.tsx']) {
            const text = readFileSync(join(SRC, rel), 'utf8');
            expect(text, `${rel} 不再通过 websocketUrl 连对局 WS`).toMatch(/websocketUrl\(`\/ws\/\$\{[^`]*`,\s*\w/);
        }
    });
});

describe('闸：持有会话 WS 的 hook，调用方必须把 token 交进去', () => {
    /**
     * 上面那组闸量错了对象 —— 它看的是 `websocketUrl()` 收没收到第二个参数，
     * 而 `useSessionBase` 一直是把自己的 `token` 变量原样递进去的，**参数在**。
     * 缺的是更外面一层：`useResearchSession()` 压根不收 token，于是递进去的是
     * `undefined`。闸全绿，研究/复盘页的 WS 在两台线上机器上却一直被
     * `close(1008, "Invalid token")`（2026-08-25 在测试机上用原始 close 帧实测：
     * 不带 token → 1008 Invalid token；带 token → 收到 game_update）。
     *
     * 所以这一条把断言落在**真正的操作数**上：谁调用这三个 hook，谁就得在选项里
     * 写出 `token`。传 `undefined` 没关系（盒子上本来就靠 cookie），但必须是
     * 显式写下来的一个决定，而不是忘了。
     *
     * 变异验证（已真跑）：把 galaxy/pages/ResearchPage.tsx 改回
     * `useResearchSession()` ⇒ 本组两条转红。
     */
    const HOOKS = ['useGameSession', 'useSessionBase', 'useResearchSession'];

    function callArgs(text: string, hook: string): string[] {
        const out: string[] = [];
        const re = new RegExp(`(\\w+\\s+)?\\b${hook}\\(`, 'g');
        for (const m of text.matchAll(re)) {
            if (m[1] && m[1].trim() === 'function') continue;   // 这是定义，不是调用
            let depth = 0;
            const start = m.index! + m[0].length;
            let i = start;
            for (; i < text.length; i++) {
                const c = text[i];
                if (c === '(' || c === '{' || c === '[') depth++;
                else if (c === ')' && depth === 0) break;
                else if (c === ')' || c === '}' || c === ']') depth--;
            }
            out.push(text.slice(start, i));
        }
        return out;
    }

    it('每个调用点都显式给出 token', () => {
        const offenders: string[] = [];
        for (const file of sourceFiles()) {
            const text = readFileSync(file, 'utf8');
            for (const hook of HOOKS) {
                for (const args of callArgs(text, hook)) {
                    if (/\btoken\s*[:,}]/.test(args)) continue;
                    offenders.push(`${relative(SRC, file)}: ${hook}(${args.trim().slice(0, 60)}) 没交 token`);
                }
            }
        }
        expect(offenders, '会话 WS 拿不到凭据 ⇒ 服务端 close(1008) ⇒ 棋盘不再更新').toEqual([]);
    });

    it('五个调用点一个都不少', () => {
        // 同样是防「整项没了」：这五个页面/hook 必须都还在开会话 WS。
        const expected: Array<[string, string]> = [
            ['galaxy/pages/GamePage.tsx', 'useGameSession'],
            ['galaxy/pages/GameRoomPage.tsx', 'useGameSession'],
            ['kiosk/pages/GamePage.tsx', 'useGameSession'],
            ['galaxy/pages/ResearchPage.tsx', 'useResearchSession'],
            ['kiosk/pages/ResearchPage.tsx', 'useResearchSession'],
        ];
        for (const [rel, hook] of expected) {
            const args = callArgs(readFileSync(join(SRC, rel), 'utf8'), hook);
            expect(args.length, `${rel} 不再调用 ${hook}`).toBeGreaterThan(0);
            expect(args.some((a) => /\btoken\s*[:,}]/.test(a)), `${rel} 的 ${hook} 没交 token`).toBe(true);
        }
    });
});
