"""Pandanet-IGS async TCP client for katrain-cron.

Connects to igs.joyjoy.net:7777 via Telnet-like text protocol.
Uses Guest login (no account needed) to list and observe professional games.

Protocol reference: qGo source (github.com/pzorin/qgo)
IGS message codes: 7=GAMES, 15=MOVE, 9=INFO, 1=PROMPT
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional

from katrain.cron import config

logger = logging.getLogger("katrain_cron.pandanet")

# IGS message type codes (client mode)
MSG_PROMPT = 1
MSG_GAMES = 7
MSG_INFO = 9
MSG_MOVE = 15


class PandanetClient:
    """Async TCP client for Pandanet-IGS."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        timeout: float = 15.0,
    ):
        self.host = host or config.PANDANET_HOST
        self.port = port or config.PANDANET_PORT
        self.timeout = timeout
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None

    # ── Connection ──────────────────────────────────────────

    async def connect(self) -> None:
        """Connect to IGS, guest login, enable client mode."""
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=self.timeout,
        )
        # Read welcome banner
        await self._read_until_prompt()
        # Login as guest
        await self._send("guest")
        await self._read_until_prompt()
        # Enable client mode for machine-parseable output
        await self._send("toggle client true")
        await self._read_until_prompt()
        logger.info("Connected to Pandanet-IGS as guest")

    async def disconnect(self) -> None:
        """Close TCP connection."""
        if self.writer:
            try:
                self._write("exit")
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
            self.writer = None
            self.reader = None

    # ── Public API ──────────────────────────────────────────

    async def get_games(self) -> list[dict]:
        """List all current games. Returns parsed game dicts."""
        await self._send("games")
        lines = await self._read_until_prompt()
        games = []
        for line in lines:
            game = _parse_game_line(line)
            if game:
                games.append(game)
        logger.debug("Parsed %d games from IGS", len(games))
        return games

    async def get_moves(self, game_id: int) -> list[str]:
        """Get move history for a game. Returns GTP coordinate list."""
        await self._send(f"moves {game_id}")
        lines = await self._read_until_prompt()
        moves = []
        for line in lines:
            move = _parse_move_line(line)
            if move:
                moves.append(move)
        return moves

    # ── Parsing helpers ─────────────────────────────────────

    @staticmethod
    def parse_match_to_row(game: dict, moves: list[str]) -> Optional[dict]:
        """Convert IGS game info + moves to a DB row dict."""
        game_id = str(game.get("id", ""))
        if not game_id:
            return None

        player_white = game.get("white_name", "")
        player_black = game.get("black_name", "")
        if not player_white or not player_black:
            return None

        return {
            "match_id": f"pandanet_{game_id}",
            "source": "pandanet",
            "source_id": game_id,
            "tournament": "Pandanet-IGS Professional Relay",
            "round_name": None,
            "match_date": datetime.now(),
            "player_black": player_black,
            "player_white": player_white,
            "black_rank": game.get("black_rank"),
            "white_rank": game.get("white_rank"),
            "status": "live",
            "result": None,
            "move_count": len(moves),
            "current_winrate": 0.5,
            "current_score": 0.0,
            "moves": moves,
            "board_size": game.get("board_size", 19),
            "komi": game.get("komi", 6.5),
            "rules": "japanese",
        }

    # ── TCP helpers ─────────────────────────────────────────

    def _write(self, cmd: str) -> None:
        if self.writer:
            self.writer.write(f"{cmd}\r\n".encode())

    async def _send(self, cmd: str) -> None:
        self._write(cmd)
        if self.writer:
            await self.writer.drain()

    async def _read_until_prompt(self, timeout: float | None = None) -> list[str]:
        """Read lines until we see a prompt (code 1)."""
        lines: list[str] = []
        t = timeout or self.timeout
        try:
            while True:
                raw = await asyncio.wait_for(self.reader.readline(), timeout=t)
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").rstrip()
                if not line:
                    continue
                # In client mode, prompt is "1 X" where X is a number
                if re.match(r"^1 \d", line):
                    break
                lines.append(line)
        except asyncio.TimeoutError:
            pass
        return lines


# ── Line parsers ────────────────────────────────────────────

# Game line format (client mode):
# 7 [227]  white_name [ 7d*] vs.  black_name [ 5d*] (250   19  2  0.5 10  I) ( 29)
_GAME_RE = re.compile(
    r"7\s+\[(\d+)\]\s+"  # game id
    r"(\S+)\s+\[\s*([^\]]*)\]\s+vs\.\s+"  # white name [rank]
    r"(\S+)\s+\[\s*([^\]]*)\]\s+"  # black name [rank]
    r"\(\s*(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+(\S)\)"  # (moves size hcap komi byo type)
    r"\s*\(\s*(\d+)\)"  # (observers)
)


def _parse_game_line(line: str) -> Optional[dict]:
    """Parse an IGS games list line into a dict."""
    m = _GAME_RE.match(line)
    if not m:
        return None
    return {
        "id": int(m.group(1)),
        "white_name": m.group(2),
        "white_rank": m.group(3).strip(),
        "black_name": m.group(4),
        "black_rank": m.group(5).strip(),
        "move_count": int(m.group(6)),
        "board_size": int(m.group(7)),
        "handicap": int(m.group(8)),
        "komi": float(m.group(9)),
        "byo_time": int(m.group(10)),
        "type": m.group(11),  # I=standard, P=professional, F=free, T=teaching
        "observers": int(m.group(12)),
    }


# Move line format (client mode):
# 15   0(B): Handicap 2
# 15   1(W): E17
# 15 249(W): J6 H6     ← move + captures
_MOVE_RE = re.compile(r"15\s+\d+\(([BW])\):\s+([A-T]\d+)")


def _parse_move_line(line: str) -> Optional[str]:
    """Parse an IGS move line into a GTP coordinate string.

    IGS coordinates (A-T skipping I, 1-19) are identical to GTP format.
    """
    m = _MOVE_RE.match(line)
    if not m:
        return None
    return m.group(2)
