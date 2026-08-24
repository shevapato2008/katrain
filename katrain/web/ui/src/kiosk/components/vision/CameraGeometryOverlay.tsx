import { useEffect, useMemo, useRef, useState } from 'react';
import type { GeometryOverlayModel, OverlayViewport } from './geometryOverlay';

/**
 * 调色板**从 CSS 读回来**,不写在这儿。
 *
 * 原来这里硬编码三个色号 `#55e68a / #ff4d4f / #ffd166` —— 一个都不是围棋的 token
 * (`go-tokens.css` 是 `#58B57A / #E2685C / #E0A24A`)。稿子把这块的配色写在
 * `.camview .quad/.g/.cor/.star` 四条 CSS 里,可这块是 `<canvas>` 不是 SVG,
 * 那四条选择器落不到它身上。⇒ 折中:**调色板仍然留在 CSS**(稿子把它放的地方),
 * 用四个自定义属性传进来,画的时候读回。这样换主题只动一处,canvas 不再自带野色号。
 */
const FALLBACK = { line: '#58B57A', corner: '#58B57A', star: '#E0A24A', stale: '#E2685C' };

function palette(el: HTMLElement) {
  const cs = getComputedStyle(el);
  const read = (name: string, fallback: string) => cs.getPropertyValue(name).trim() || fallback;
  return {
    line: read('--cam-line', FALLBACK.line),
    corner: read('--cam-corner', FALLBACK.corner),
    star: read('--cam-star', FALLBACK.star),
    stale: read('--cam-stale', FALLBACK.stale),
  };
}

/** 四角就是这四个交叉点。锚点按**它是什么**上色,不按「哪种颜色的灯照出来的」。 */
function isCorner(row: number, col: number, size = 19): boolean {
  return (row === 0 || row === size - 1) && (col === 0 || col === size - 1);
}

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

    const pal = palette(canvas);
    // `stale` = 几何已经不可信(盘被挪过)。整块红,和「正常」一眼分得开。
    const color = model.tone === 'stale' ? pal.stale : pal.line;
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
    // 九星走琥珀、四角走绿 —— 稿子 `.camview .star{fill:var(--warn)}` / `.cor{fill:var(--accent)}`。
    context.fillStyle = model.tone === 'stale' ? pal.stale : pal.star;
    for (const point of model.starPoints) {
      context.beginPath();
      context.arc(point.x, point.y, 4, 0, Math.PI * 2);
      context.fill();
    }
    for (const anchor of model.anchors) {
      /**
       * 上一版按**LED 灯色**上色(绿/红/蓝 = 标定器第几次尝试用的颜色)。撤掉:
       * 屏上没有一个字解释那三种颜色是什么意思,而「哪种颜色的灯找到的」今天**没有消费者**
       * —— 它只落在后端的 `attempts` 里,不出接口。调 LED 的人看那份日志,不看这块画面。
       * 改成按**这个点是什么**上色:四角绿、星位琥珀,和稿子那 4+9 个点逐一对上。
       */
      context.fillStyle = isCorner(anchor.row, anchor.col) ? pal.corner : pal.star;
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
      context.fillStyle = model.tone === 'stale' ? pal.stale : pal.corner;
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
