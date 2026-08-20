/**
 * 组标题行:中文 12.5px Sans 700 .12em + 英文 11px Serif 斜体 `--dim` + 渐隐横线
 * + 右端可选的值(`.secval`)。容器几何在 tokens.css:563-566,四个子元素在 seclabel.css。
 *
 * 右端那个值是**数据**(「本机 5 局」「两档:500 / 2000 次计算」),不是旁注。
 * 稿子里的解释性段落(`.note`)是给读稿人看的,不进这里,也不上线 —— 见 G5。
 */
export function KioskSecLabel({ zh, en, value }: { zh: string; en: string; value?: string }) {
  return (
    <div className="kiosk-seclabel">
      <h2>{zh}</h2>
      <em>{en}</em>
      <span className="rule" />
      {value && <b className="secval">{value}</b>}
    </div>
  );
}
