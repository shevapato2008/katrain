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
