import React from 'react';
import { createRoot } from 'react-dom/client';
import { GoBoardSvg } from '../../src/kiosk/shell/GoBoardSvg';
import { BOARD_ASSETS } from '../../src/components/board/boardUtils';
import boardImage from '../../../../img/board.png';
import '../../src/kiosk-shell/go-tokens.css';
import '../../src/kiosk-shell/go-screens.css';

const white = ['Q16', 'R15', 'P14', 'N12', 'K10', 'F8', 'D5', 'C4', 'M4', 'S3'];
const black = ['D16', 'F16', 'C14', 'E13', 'H12', 'M10', 'R10', 'Q8', 'G6', 'K4'];

document.body.style.cssText = 'margin:0;background:#07130e;color:#e5efe7;font:22px sans-serif';
BOARD_ASSETS.board = boardImage;
createRoot(document.getElementById('root')!).render(
  <main className="kiosk" style={{ display: 'flex', gap: 38, alignItems: 'flex-start', padding: 24 }}>
    <div style={{ width: 520 }}><GoBoardSvg black={black} white={white} /></div>
    <div><p style={{ marginTop: 0 }}>实尺寸棋盘</p><div style={{ width: 220 }}><GoBoardSvg black={black} white={white} /></div></div>
  </main>,
);
