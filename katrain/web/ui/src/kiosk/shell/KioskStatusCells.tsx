export interface StatusCell { label: string; value: string; tone?: 'good' | 'warn' | 'bad' }

/**
 * §5 状态格。几何写死(三格 84×56、格内文字垂直居中,`tokens.css:461-474`),
 * **填什么由模块决定**:硬件状态(对弈/训练营/课程/棋谱)、本局指标(复盘)、分数摘要(成长)。
 *
 * 灯色语义四棋类统一:绿=正常、琥珀=需处理、红=故障。器件名各家跟着**自己盘上真有的东西**走 ——
 * 国象/象棋盘上没有摄像头,五子棋盘上没有 LED。说明书上没有的东西,界面上不能有。
 *
 * 围棋自己那三格在 `goHardware.ts` —— 常量和组件不同住,`react-refresh/only-export-components`
 * 要求一个文件只导出组件。
 *
 * DOM 逐字取自稿子的 `[data-status]` 填充脚本(`go-kiosk.tmpl.html:823-829`):
 * `__k` 和 `__v` 都是 `<div>`。计划里写的是 `<span>` / `<b>`,渲染结果一样
 * (字重字号全由 CSS 给),但这是搬运 —— 有正本就照正本。
 */
export function KioskStatusCells({ cells }: { cells: readonly StatusCell[] }) {
  return (
    <div className={`kiosk-status${cells.length === 2 ? ' kiosk-status--2' : ''}`}>
      {cells.map((c) => (
        <div className="kiosk-status__cell" key={c.label}>
          <div className="kiosk-status__k">
            {c.tone && <i style={{ color: `var(--${c.tone})` }} />}{c.label}
          </div>
          <div className="kiosk-status__v">{c.value}</div>
        </div>
      ))}
    </div>
  );
}
