import '@testing-library/jest-dom';

// Node's experimental global localStorage can leave Vitest's jsdom window
// without a storage instance. Keep the browser contract available to tests.
if (!window.localStorage) {
  const values = new Map<string, string>();
  const storage: Storage = {
    get length() { return values.size; },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => Array.from(values.keys())[index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
  };
  Object.defineProperty(window, 'localStorage', { configurable: true, value: storage });
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: storage });
}

// Polyfill ResizeObserver for jsdom (used by LiveBoard, TsumegoBoard)
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Stub HTMLCanvasElement.getContext for jsdom (canvas boards render via 2D context)
HTMLCanvasElement.prototype.getContext = (() => null) as never;

// jsdom does not define window.WebGLRenderingContext (unlike real browsers with WebGL).
// Stub it so WebGL-availability checks (e.g. the kiosk 3D toggle guard) see "available" by
// default, matching production browsers. Tests that need to simulate no-WebGL should use
// vi.stubGlobal('WebGLRenderingContext', undefined) and vi.unstubAllGlobals() after.
if (typeof window.WebGLRenderingContext === 'undefined') {
  (window as unknown as { WebGLRenderingContext: unknown }).WebGLRenderingContext = function WebGLRenderingContext() {};
}

// jsdom 没有 `Element.prototype.scrollIntoView`(真浏览器全都有)。屏 07 聚焦输入框时
// 会调它把那一格滚进视野 —— 少了它,rAF 里抛出的 TypeError 是**未捕获异常**,
// vitest 会把它算成一次 unhandled error,污染整轮的判读。
// 这是**脚手架**:滚没滚到位归真浏览器那条承重闸(`tests/kiosk-shell-scroll.spec.ts`
// 里「聚焦验证码那一格时,它整个在软键盘上缘之上」),jsdom 对此无权作证。
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {};
}

// jsdom 的 `HTMLMediaElement.prototype.play()` 返回 undefined,真浏览器返回 Promise。
// 产品代码一律写 `audio.play().catch(...)` ⇒ jsdom 里 `.catch` 当场抛 TypeError。
// 赢棋庆祝(`kiosk/hooks/useGameCelebration.ts`)在 rAF 里播音,抛出来是**未捕获异常**,
// 而且只在 rAF 赶在用例结束前触发时才出现:单独跑 `GamePageEngine.test.tsx` 三次 0 次,
// 全量跑(负载高、用例变慢)才冒出 1 次 —— 时序决定,不是哪条改动引入的。
// 这是**脚手架**:响没响、何时响归真浏览器,jsdom 对此无权作证。
HTMLMediaElement.prototype.play = function play() {
  return Promise.resolve();
};
