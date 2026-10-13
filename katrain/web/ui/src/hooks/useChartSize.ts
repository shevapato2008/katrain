import { useCallback, useEffect, useRef, useState } from 'react';

/** Measure the plot, so SVG text and stones keep their CSS-pixel size. */
export function useChartSize(width = 320, height = 240) {
  const [size, setSize] = useState({ width, height });
  const observer = useRef<ResizeObserver | null>(null);
  const ref = useCallback((node: HTMLDivElement | null) => {
    observer.current?.disconnect();
    if (!node) return;
    const read = () => {
      const rect = node.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) setSize(previous => {
        const next = { width: Math.floor(rect.width), height: Math.floor(rect.height) };
        return previous.width === next.width && previous.height === next.height ? previous : next;
      });
    };
    read();
    observer.current = new ResizeObserver(read);
    observer.current.observe(node);
  }, []);
  useEffect(() => () => observer.current?.disconnect(), []);
  return [ref, size] as const;
}
