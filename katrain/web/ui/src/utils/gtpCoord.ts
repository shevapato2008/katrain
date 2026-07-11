// GTP-style coordinate label formatting (col letter + row number), shared between the
// AI-move banner (GamePage.tsx) and the physical engine-move error dialog (Task 9).
// `col`/`row` are GTP/board space (col 0-indexed A.., row 0 = bottom) — the SAME
// convention used by GameState.last_move and the `physical_engine_error` WS broadcast's
// col/row fields (see physical_play_orchestrator.py's enter_engine_error docstring).
// Extracted verbatim from the pre-Task-9 AI-move banner formula — do not "fix" the
// row math here without also checking every existing caller's expectations (tests pin
// last_move=[3,3], board_size=19 -> "D16").
export function formatGtpCoord(col: number, row: number, boardSize: number): string {
  const colLabel = String.fromCharCode(65 + (col >= 8 ? col + 1 : col)); // skip 'I'
  const rowLabel = boardSize - row;
  return `${colLabel}${rowLabel}`;
}
