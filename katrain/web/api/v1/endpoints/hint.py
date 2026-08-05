"""POST /api/v1/hint — AI 支招: top-N candidate points, white blinking LEDs on the
physical board, detection suspended while shown (PRD R4)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from katrain.web.core.hint_gate import DefaultHintGate
from katrain.web.core.physical_play import PhysicalPlayConfig
from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core.ranked_session_guard import guard_user_has_no_pending_ranked_game, temporary_analysis_lease
from katrain.web.models import User

router = APIRouter()


class HintRequest(BaseModel):
    session_id: str
    top_n: Optional[int] = Field(default=None, ge=1, le=10)


def _build_payload_from_game(game, max_visits: int) -> dict:
    """KataGo analysis payload for the current position — mirrors KaTrain's own
    query builder (BaseEngine.request_analysis, katrain/core/engine.py:123-190,
    review Codex I2): moves AND placements are collected from EVERY node on the
    path (setup stones can appear mid-tree), AE/clear_placements is unsupported
    (KaTrain's builder refuses such positions too), and initialPlayer matters
    for handicap games (White moves first)."""
    nodes = game.current_node.nodes_from_root
    moves = [m for node in nodes for m in node.moves]
    initial_stones = [m for node in nodes for m in node.placements]
    if any(node.clear_placements for node in nodes):
        raise ValueError("unsupported position: AE (clear placements) in game path")
    size_x, size_y = game.board_size
    return {
        "rules": game.current_node.ruleset or "chinese",
        "komi": game.komi,
        "boardXSize": size_x,
        "boardYSize": size_y,
        "analyzeTurns": [len(moves)],
        "maxVisits": max_visits,
        "includeOwnership": False,
        "includePolicy": False,
        "initialStones": [[m.player, m.gtp()] for m in initial_stones],
        "initialPlayer": game.current_node.initial_player,
        "moves": [[m.player, m.gtp()] for m in moves],
    }


@router.post("")
async def request_hint(request: Request, body: HintRequest, current_user: User = Depends(get_current_user)):
    guard_user_has_no_pending_ranked_game(request.app, current_user, "hint")
    manager = request.app.state.session_manager
    try:
        session = manager.get_session(body.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    katrain = session.katrain
    game_type = getattr(katrain, "game_type", "free")
    # D3 double gate: analysis_allowed (anti-cheat chokepoint semantics) AND free-only scene.
    if not getattr(katrain, "analysis_allowed", True) or game_type != "free":
        raise HTTPException(status_code=403, detail="hint not allowed in this game")

    config: PhysicalPlayConfig = getattr(request.app.state, "physical_play_config", None) or PhysicalPlayConfig()
    gate = getattr(request.app.state, "hint_gate", None) or DefaultHintGate(config.hint_engine)
    decision = gate.check(game_type=game_type, user_id=getattr(session, "user_id", None))
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)

    router_instance = getattr(request.app.state, "router", None)
    if router_instance is None:
        raise HTTPException(status_code=503, detail="engine not available")

    try:
        payload = _build_payload_from_game(katrain.game, config.hint_max_visits)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    payload["is_analysis"] = decision.engine == "cloud"  # RequestRouter: cloud-preferred routing
    try:
        with temporary_analysis_lease(request.app, current_user, body.session_id, "hint", "hint"):
            result = await router_instance.route(payload)
            from katrain.core.game import Move

            top_n = body.top_n or config.hint_top_n
            board_size = katrain.game.board_size[0]
            moves = []
            for info in sorted(result.get("moveInfos", []), key=lambda m: m.get("order", 999)):
                if len(moves) >= top_n:
                    break
                gtp = info.get("move", "pass")
                if gtp.lower() == "pass":
                    continue
                x, y = Move.from_gtp(gtp).coords
                moves.append(
                    {
                        "gtp": gtp,
                        "coords": [x, y],
                        "vision_rc": [board_size - 1 - y, x],
                        "winrate": info.get("winrate"),
                        "score_lead": info.get("scoreLead"),
                        "visits": info.get("visits"),
                    }
                )

            orchestrator = getattr(request.app.state, "physical_play", None)
            if orchestrator is not None and moves:
                orchestrator.show_hint([tuple(m["vision_rc"]) for m in moves])
            gate.settle(decision.charge_ref, success=True)
            return {"moves": moves, "engine": result.get("engine", decision.engine), "timeout_s": config.hint_timeout_s}
    except HTTPException:
        gate.settle(decision.charge_ref, success=False)
        raise
    except Exception as e:
        gate.settle(decision.charge_ref, success=False)
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/dismiss")
async def dismiss_hint(request: Request):
    orchestrator = getattr(request.app.state, "physical_play", None)
    if orchestrator is not None:
        orchestrator.dismiss_hint()
    return {"ok": True}
