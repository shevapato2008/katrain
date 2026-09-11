/**
 * 手机验证码四个 API（P3 / Task 13）。
 *
 * 三档门控照 `src/context/AuthContext.test.tsx:42-48` 的现成写法（那里是四档，
 * 本文件只需要 strict / 非 strict 两档）。跑严格盒端那一档要带两个环境变量：
 *   VITE_KIOSK_2D_ONLY=true VITE_BOX_SSO_STRICT=true npx vitest run src/api.phone.test.ts
 * 这一对与 package.json:10 的 `build:smartbox-kiosk-2d` 用的是同一对，所以两者可对齐。
 *
 * ⚠️ 判读时别只看 passed/skipped 的**数字** —— 裸跑与 legacy-kiosk 档的汇总数字可能相同，
 * 只有用例名能分辨。要确认换档成功就加 `--reporter=verbose`（`--reporter=basic` 在
 * vitest 4 已被移除，会直接报错退出）。
 *
 * ⚠️ 本文件的类型**没有任何一层在检查**：`tsconfig.app.json:28` 把 src 下的测试文件
 * exclude 掉了，而 vitest 不做类型检查（vite.config.ts 的 test 段没有 typecheck）。
 * （别在这段块注释里写 glob —— 双星斜杠里的那个 `*` 加 `/` 会把注释提前关掉，实测过。）
 * 所以这里的 `as Response` 之类断言全无编译期守卫，只有真跑才算数。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { API, ApiError } from './api';

const isKioskBuild = __KIOSK_2D_ONLY__;
const isStrictBoxKiosk = isKioskBuild && import.meta.env.VITE_BOX_SSO_STRICT === 'true';
const nonStrictIt = isStrictBoxKiosk ? it.skip : it;
const strictKioskIt = isStrictBoxKiosk ? it : it.skip;

const jsonResponse = (body: unknown, status = 200) =>
  Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response);

const headersOf = (init?: RequestInit) => (init?.headers ?? {}) as Record<string, string>;

describe('手机验证码四个 API', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // localStorage 在严格盒端那一档也要有值 —— 否则「不带 Authorization」那条断言
    // 会因为压根没 token 而假绿（它在两档里都要真的有东西可漏才算守住）。
    // `configurable: true` 是必需的：反复 defineProperty 同一个属性，不可配置时第二次抛
    // `TypeError: Cannot redefine property`。（AuthContext.test.tsx:25-27 那句没写它，
    // 因为它在模块顶层只执行一次；搬进 beforeEach 就必须加。）
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (k: string) => (k === 'token' ? 'stored-token' : null),
        setItem: () => {}, removeItem: () => {}, clear: () => {},
      },
    });
  });

  it('sendPhoneCode 打到 send-code，并把 purpose 一起送出去', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      jsonResponse({ challenge_id: 'c1', cooldown_sec: 60 }));
    await API.sendPhoneCode('+8613800138000', 'login');
    const [url, init] = f.mock.calls[0];
    expect(url).toBe('/api/v1/auth/phone/send-code');
    expect(JSON.parse(init!.body as string)).toEqual({ phone: '+8613800138000', purpose: 'login' });
  });

  it('loginByPhone 只送 challenge_id 与 code —— 不送手机号', async () => {
    // spec §2「verify 只收 challenge_id 不收手机号」的前端一半：
    // 前端多送一个 phone，后端哪天顺手信了它，验证码就和号解耦了。
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      jsonResponse({ access_token: 't', token_type: 'bearer' }));
    await API.loginByPhone('c1', '123456');
    const body = JSON.parse((f.mock.calls[0][1] as RequestInit).body as string);
    expect(body).toEqual({ challenge_id: 'c1', code: '123456' });
    expect(Object.keys(body)).not.toContain('phone');
  });

  it('setPassword 的字段名是 new_password，URL 是 set-password（下划线 vs 连字符）', async () => {
    // 后端 purpose 写 `set_password`（下划线）而路径是 `/auth/set-password`（连字符）,
    // 这是本组四个端点里最容易写错的一处；写错的表现是 422,而 422 的 detail 是**数组**,
    // 于是 UI 上只会看到一句通用失败 —— 静默程度很高,值一条用例。
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() => jsonResponse({ ok: true }));
    await API.setPassword('c1', '123456', 'pw');
    expect(f.mock.calls[0][0]).toBe('/api/v1/auth/set-password');
    expect(JSON.parse((f.mock.calls[0][1] as RequestInit).body as string))
      .toEqual({ challenge_id: 'c1', code: '123456', new_password: 'pw' });
  });

  it('限流时把后端的 code 与 retry_after_sec 原样抛出去，并且它是 ApiError 的子类', async () => {
    // `instanceof ApiError` 这一半不是凑数：本仓已经因为「另起一个不继承 ApiError 的
    // 错误类」出过一次缺陷,并有用例钉着 —— galaxy/pages/AiSetupPage.test.tsx:747
    // 「AiLadderApiError 不是 ApiError 的子类」⇒ 按 instanceof 分流的登录引导成了死代码,
    // 屏上退回一串裸报文。新错误继承 ApiError,既有的 instanceof 消费者才认得它。
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      jsonResponse({ detail: { code: 'sms_cooldown', retry_after_sec: 42 } }, 429));
    const err = await API.sendPhoneCode('+8613800138000', 'login').catch(e => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ code: 'sms_cooldown', retryAfterSec: 42, status: 429 });
  });

  it('detail 不是对象时不瞎解析 —— 401 是字符串、422 是数组', async () => {
    // **后端的 detail 并非一律是对象**（本轮实测）：
    //   401 `detail: "Not authenticated"`（auth.py:214-218 / :190-194）—— 字符串;
    //   422 `detail: [{loc, msg, type}, ...]`（pydantic 校验失败，FastAPI 默认形状）—— 数组。
    // `typeof [] === "object"` ⇒ 只判 typeof 会把数组当成 detail 收下,
    // 于是 `err.code` 是 undefined 而调用方以为自己拿到了一个「有 code 的错误」。
    // 判据:这两种情况下 code 必须是 undefined、status 必须准确 —— 让 UI 能按 status 分流。
    for (const [status, detail] of [[401, 'Not authenticated'], [422, [{ loc: ['body', 'phone'] }]]] as const) {
      vi.spyOn(globalThis, 'fetch').mockImplementation(() => jsonResponse({ detail }, status));
      const err = await API.bindPhone('c1', '123456').catch(e => e);
      expect(err.status).toBe(status);
      expect(err.code).toBeUndefined();
      expect(err.retryAfterSec).toBeUndefined();
    }
  });

  it('register 的请求体没有被改动 —— 共享领土，ZenModeApp / RegisterDialog 也在用', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() => jsonResponse({}));
    await API.register('u', 'p');
    expect(f.mock.calls[0][0]).toBe('/api/v1/auth/register');
    expect(JSON.parse((f.mock.calls[0][1] as RequestInit).body as string))
      .toEqual({ username: 'u', password: 'p' });
  });

  nonStrictIt('bindPhone 带鉴权头（它是鉴权端点）', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      jsonResponse({ phone_masked: '+86 138****8000' }));
    await API.bindPhone('c1', '123456');
    expect(headersOf(f.mock.calls[0][1] as RequestInit).Authorization).toBe('Bearer stored-token');
  });

  it('sendPhoneCode 不带鉴权头 —— 它是不鉴权端点，递 token 只是多一个外泄面', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      jsonResponse({ challenge_id: 'c1', cooldown_sec: 60 }));
    await API.sendPhoneCode('+8613800138000', 'login');
    expect(headersOf(f.mock.calls[0][1] as RequestInit).Authorization).toBeUndefined();
  });

  strictKioskIt('严格盒端下 bindPhone 也不造 Bearer 头 —— 身份只走 HttpOnly cookie', async () => {
    // 这条是本 Task 唯一挡得住「自己再写一个取 token 的助手」的闸：
    // 手搓的助手不会有 api.ts:298 那句 `if (isStrictBoxKiosk) return {}`，
    // 于是 localStorage 里那个陈旧 token 会被塞进请求，把盒端的 cookie 契约压过去。
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      jsonResponse({ phone_masked: '+86 138****8000' }));
    await API.bindPhone('c1', '123456');
    expect(headersOf(f.mock.calls[0][1] as RequestInit).Authorization).toBeUndefined();
  });
});
