import { useEffect, useMemo, useRef, useState } from 'react';
import type { GeometryOverlayModel, OverlayViewport } from './geometryOverlay';

const COLORS = {
  normal: '#55e68a',
  stale: '#ff4d4f',
  partial: '#ffd166',
};

const ANCHOR_COLORS: Record<string, string> = {
  green: '#55e68a',
  red: '#ff4d4f',
  blue: '#4da3ff',
};

const CameraGeometryOverlay = ({
  modelForViewport,
  label,
}: {
  modelForViewport: (viewport: OverlayViewport) => GeometryOverlayModel | null;
  label: string;
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const model = useMemo(
    () => size.width > 0 && size.height > 0 ? modelForViewport(size) : null,
    [modelForViewport, size],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver(([entry]) => {
      const width = entry.contentRect.width;
      const height = entry.contentRect.height;
      setSize((current) => current.width === width && current.height === height ? current : { width, height });
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context || size.width <= 0 || size.height <= 0) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(size.width * dpr);
    canvas.height = Math.round(size.height * dpr);
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    context.clearRect(0, 0, size.width, size.height);
    if (!model) return;

    const color = COLORS[model.tone];
    context.strokeStyle = color;
    context.fillStyle = color;
    context.globalAlpha = model.tone === 'stale' ? 0.78 : 0.68;
    context.lineWidth = model.tone === 'stale' ? 2 : 1;
    for (const line of model.lines) {
      context.beginPath();
      context.moveTo(line.from.x, line.from.y);
      context.lineTo(line.to.x, line.to.y);
      context.stroke();
    }
    for (const point of model.points) {
      context.beginPath();
      context.arc(point.x, point.y, 1.7, 0, Math.PI * 2);
      context.fill();
    }
    context.globalAlpha = 0.95;
    for (const point of model.starPoints) {
      context.beginPath();
      context.arc(point.x, point.y, 4, 0, Math.PI * 2);
      context.fill();
    }
    for (const anchor of model.anchors) {
      context.fillStyle = ANCHOR_COLORS[anchor.color] ?? COLORS.partial;
      context.beginPath();
      context.arc(anchor.x, anchor.y, 7, 0, Math.PI * 2);
      context.fill();
      context.strokeStyle = '#111';
      context.lineWidth = 2;
      context.stroke();
    }
    context.font = '600 13px "Noto Sans SC", sans-serif';
    context.textBaseline = 'bottom';
    for (const corner of model.corners) {
      context.fillStyle = color;
      context.beginPath();
      context.arc(corner.x, corner.y, 6, 0, Math.PI * 2);
      context.fill();
      const textX = Math.min(Math.max(corner.x + 8, 4), size.width - 42);
      const textY = Math.min(Math.max(corner.y - 8, 18), size.height - 2);
      context.fillStyle = 'rgba(0, 0, 0, 0.72)';
      context.fillRect(textX - 3, textY - 15, 42, 18);
      context.fillStyle = color;
      context.fillText(corner.label, textX, textY);
    }
    context.globalAlpha = 1;
  }, [model, size]);

  return (
    <canvas
      ref={canvasRef}
      aria-label={label}
      data-tone={model?.tone ?? 'none'}
      data-lines={model?.lines.length ?? 0}
      data-points={model?.points.length ?? 0}
      data-corners={model?.corners.length ?? 0}
      data-anchors={model?.anchors.length ?? 0}
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
    />
  );
};

export default CameraGeometryOverlay;
