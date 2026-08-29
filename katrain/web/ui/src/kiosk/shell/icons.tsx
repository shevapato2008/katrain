// Phosphor v2(MIT)。规范 §10:图标只能从 Phosphor v2 出、成对导出,四个前端用**同一份字节**
// —— 所以 `src/kiosk-shell/icons/` 是整目录抄来的 82 个文件(41 对),不挑,由
// `kiosk-shell/MANIFEST.sha256` 钉住(290 行)。
//
// `?raw` 拿源码内联,**不能**用 `<img src>`:<img> 跟不了容器的 `color`,而
// `.kiosk-dock__item[aria-current="page"] { color: var(--ink) }` 翻色全靠 `currentColor`,
// 选中那一格的图标会一直是灰的。
//
// `eager: true` 把 82 个一次性打进包:全部加起来 40KB 源码,分块的收益小于多一层动态
// import 的复杂度(而且 kiosk 是离线盒子,没有"按需拉"这回事)。
const modules = import.meta.glob('../../kiosk-shell/icons/*.svg', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>;

const table: Record<string, string> = {};
for (const [path, source] of Object.entries(modules)) {
  // `.trim()`:svg 文件末尾那个换行会变成 `.kiosk-icon` 里的一个空白文本节点。
  // 布局上无害(flex 容器忽略纯空白匿名盒),但它会混进 textContent ——
  // Dock 项读出来就成了 "\n对弈"。
  table[path.split('/').pop()!.replace(/\.svg$/, '')] = source.trim();
}

/**
 * 目录里 41 个基础名(每个都还有一份 `-fill`)。
 *
 * **手写的**:TS 推不出 `import.meta.glob` 的键,拿不到字面量联合。手写就会和目录漂,
 * 所以 `icons.test.tsx` 里有两条把这份名单和真实目录对死的断言,两个方向都堵 ——
 * 名单里有而目录里没有(会在屏上抛)、目录里有而名单里没有(等于抄进来却永远用不到)。
 */
export const ICON_NAMES = [
  'arrow-clockwise', 'arrow-counter-clockwise', 'arrow-left', 'arrow-right',
  'arrows-clockwise', 'book-open', 'books', 'broadcast', 'camera',
  'caret-double-left', 'caret-double-right', 'caret-down', 'caret-left', 'caret-right',
  'circuitry', 'corners-out', 'crown-simple', 'cube', 'flag', 'game-controller', 'gear',
  'globe-hemisphere-west', 'grid-nine', 'hand-pointing', 'handshake', 'house', 'info',
  'lightbulb', 'magnifying-glass', 'puzzle-piece', 'qr-code', 'robot', 'skip-forward',
  'sliders-horizontal', 'speaker-high', 'squares-four', 'trend-up', 'trophy',
  'upload-simple', 'user-circle', 'users',
] as const;

export type IconName = (typeof ICON_NAMES)[number];

export function Icon({ name, filled = false }: { name: IconName; filled?: boolean }) {
  const key = filled ? `${name}-fill` : name;
  const source = table[key] ?? table[name];
  if (!source) {
    // 缺图标要**响**,不要静默画个空盒子 —— 静默的话屏上少一个图标没人发现。
    throw new Error(`图标不在 kiosk-shell/icons/ 里:${key}`);
  }
  return <span className="kiosk-icon" aria-hidden="true" dangerouslySetInnerHTML={{ __html: source }} />;
}

/** 名单闸自己要查目录,这两个只给测试用,不是渲染路径的一部分。 */
Icon.has = (file: string): boolean => file in table;
Icon.all = (): string[] => Object.keys(table);
