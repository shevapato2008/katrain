import '@testing-library/jest-dom';

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
