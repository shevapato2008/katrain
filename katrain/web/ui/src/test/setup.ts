import '@testing-library/jest-dom';

// Polyfill ResizeObserver for jsdom (used by LiveBoard, TsumegoBoard)
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Stub HTMLCanvasElement.getContext for jsdom (canvas boards render via 2D context)
HTMLCanvasElement.prototype.getContext = (() => null) as never;
