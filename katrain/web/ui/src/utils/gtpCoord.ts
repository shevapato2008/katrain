// GTP-style coordinate label formatting (col letter + row number), shared between the
// AI-move banner (GamePage.tsx) and the physical engine-move error dialog (Task 9).
// `col`/`row` are core/GTP space, row 0 = BOTTOM — the SAME convention used by
// GameState.last_move and the `physical_engine_error` WS broadcast's col/row fields
// (both pass core coords straight through with no pre-flip). GTP row numbers count
// from the bottom starting at 1, so the label is simply `row + 1` (col=3,row=3,
// board_size=19 -> "D4"; do not re-derive this from board_size — the label doesn't
// depend on it).
export function formatGtpCoord(col: number, row: number, _boardSize: number): string {
  const colLabel = String.fromCharCode(65 + (col >= 8 ? col + 1 : col)); // skip 'I'
  const rowLabel = row + 1;
  return `${colLabel}${rowLabel}`;
}
