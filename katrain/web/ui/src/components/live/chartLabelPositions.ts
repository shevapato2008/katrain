/** Place compact move numbers clear of every stone and already placed label. */
export function placeChartLabels(
  points: readonly { x: number; y: number; label: string; black: boolean }[],
  bounds: { left: number; right: number; top: number; bottom: number },
): ({ x: number; y: number } | null)[] {
  const used: { left: number; right: number; top: number; bottom: number }[] = [];
  return points.map(point => {
    const halfWidth = point.label.length * 3.7 + 2;
    const dy = point.black ? -12 : 22;
    for (const [dx, offset] of [[0, dy], [halfWidth + 10, 4], [-halfWidth - 10, 4], [0, -dy], [halfWidth + 10, dy], [-halfWidth - 10, dy]]) {
      const x = point.x + dx;
      const y = point.y + offset;
      const box = { left: x - halfWidth, right: x + halfWidth, top: y - 12, bottom: y + 3 };
      if (box.left < bounds.left || box.right > bounds.right || box.top < bounds.top || box.bottom > bounds.bottom) continue;
      if (used.some(other => box.left < other.right + 3 && box.right > other.left - 3 && box.top < other.bottom + 3 && box.bottom > other.top - 3)) continue;
      if (points.some(other => other.x + 8 > box.left && other.x - 8 < box.right && other.y + 8 > box.top && other.y - 8 < box.bottom)) continue;
      used.push(box);
      return { x, y };
    }
    return null; // the point's title/click still exposes it in very dense positions
  });
}
