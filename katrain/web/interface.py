import logging
from typing import Callable, Optional

from katrain.web.kivy_compat import ensure_kivy

ensure_kivy()

from katrain.core.base_katrain import KaTrainBase
from katrain.core.constants import (
    MODE_ANALYZE,
    MODE_PLAY,
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
    OUTPUT_INFO,
    PLAYING_NORMAL,
)
from katrain.core.engine import create_engine
from katrain.core.game import Game

# Configure standard logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("katrain_web")


class NullEngine:
    def on_new_game(self):
        return None

    def request_analysis(self, *_args, **_kwargs):
        return None

    def terminate_queries(self, *_args, **_kwargs):
        return None

    def stop_pondering(self):
        return None

    def shutdown(self, finish=False):
        return None


class MockControls:
    def __init__(self, katrain):
        self.katrain = katrain

    def set_status(self, message, level=OUTPUT_INFO, **_kwargs):
        self.katrain.log(message, level)


class WebKaTrain(KaTrainBase):
    """
    A headless version of KaTrain for the Web UI.
    """

    def __init__(self, force_package_config=False, debug_level=None, enable_engine=True, **kwargs):
        # Initialize base without invoking Kivy-specifics that might break headless if possible.
        # KaTrainBase __init__ is relatively safe, mostly config and logging.
        super().__init__(force_package_config, debug_level, **kwargs)

        try:
            from kivymd.app import MDApp
            MDApp.gui = self
        except Exception:
            pass

        self.engine = None
        self.enable_engine = enable_engine
        self.update_state_callback: Optional[Callable] = None
        self.message_callback: Optional[Callable] = None
        self.controls = MockControls(self)
        self.play_analyze_mode = MODE_PLAY
        self.pondering = False

    def start(self):
        """Initializes the engine and starts a new game."""
        if self.engine:
            return

        # Load trainer config
        # In KaTrainGui, this is self.board_gui.trainer_config = self.config("trainer")
        # We might need to store this locally or pass it to whatever needs it.
        # For now, we assume the engine uses self.config directly where needed, 
        # or we might need to mock board_gui if it's deeply integrated.
        # Checking KataGoEngine: it takes (katrain, config). 
        # It calls katrain.log, katrain("engine_recovery_popup"), etc.
        
        if self.enable_engine:
            try:
                self.engine = create_engine(self, self.config("engine"))
            except Exception as exc:
                self.log(f"Engine startup failed, falling back to NullEngine: {exc}", OUTPUT_ERROR)
                self.engine = NullEngine()
        else:
            self.engine = NullEngine()

        # Start a new game
        self._do_new_game()

    def log(self, message, level=OUTPUT_INFO):
        """Redirect logs to Python logger."""
        message = str(message)
        if level == OUTPUT_ERROR:
            logger.error(message)
        elif level == OUTPUT_DEBUG:
            logger.debug(message)
        else:
            logger.info(message)
        
        # In the future, we might want to push logs to the client via WebSocket
        if self.message_callback:
            self.message_callback("log", {"message": message, "level": level})

    def get_state(self):
        """Returns a JSON-serializable representation of the current game state."""
        if not self.game:
            return {"error": "No game active"}

        cn = self.game.current_node
        last_move = cn.move.coords if cn.move else None

        # Get history of nodes from root to current
        history = []
        nodes = []
        node = cn
        while node:
            nodes.append(node)
            node = node.parent
        nodes.reverse()

        for node in nodes:
            history.append({
                "node_id": id(node),
                "score": node.score if node.analysis_exists else None,
                "winrate": node.winrate if node.analysis_exists else None,
            })
        current_node_index = len(history) - 1

        # Format stones with evaluation
        stones_with_eval = []
        # We can reconstruct board state evaluation by looking at the nodes in the current path
        # Actually, self.game.stones returns stones on the board for the current node.
        # To get evaluation for each stone, we map coordinates to nodes in history.
        coord_to_eval = {}
        for h_node in nodes:
            if h_node.move and h_node.move.coords:
                coord_to_eval[h_node.move.coords] = h_node.points_lost

        for move in self.game.stones:
            player, coords = move.player, move.coords
            score_loss = coord_to_eval.get(tuple(coords)) if coords else None
            stones_with_eval.append([player, list(coords) if coords else None, score_loss])

        # Format analysis data for the frontend
        analysis = None
        if cn.analysis and cn.analysis.get("root"):
            root = cn.analysis["root"]
            moves = []
            from katrain.core.sgf_parser import Move
            for gtp, move_info in cn.analysis.get("moves", {}).items():
                try:
                    m = Move.from_gtp(gtp)
                    moves.append({
                        **move_info,
                        "move": gtp,
                        "coords": list(m.coords) if m.coords else None,
                        "scoreLoss": move_info.get("scoreLoss", 0),
                        "winrate": move_info.get("winrate", 0),
                        "visits": move_info.get("visits", 0),
                    })
                except Exception:
                    pass
            # Sort moves by visits descending
            moves.sort(key=lambda x: x.get("visits", 0), reverse=True)

            from katrain.core.utils import var_to_grid
            sz = self.game.board_size
            ownership_grid = None
            if cn.analysis.get("ownership"):
                ownership_grid = var_to_grid(cn.analysis["ownership"], sz)
            
            policy_grid = None
            if cn.analysis.get("policy"):
                policy_grid = var_to_grid(cn.analysis["policy"][:-1], sz) # exclude pass

            analysis = {
                "winrate": root.get("winrate", 0.5),
                "score": root.get("scoreLead", 0),
                "visits": root.get("visits", 0),
                "moves": moves,
                "ownership": ownership_grid,
                "policy": policy_grid,
            }

        return {
            "game_id": self.game.game_id,
            "board_size": list(self.game.board_size),
            "komi": self.game.komi,
            "handicap": int(self.game.root.handicap or 0),
            "ruleset": cn.ruleset,
            "current_node_id": id(cn),
            "current_node_index": current_node_index,
            "history": history,
            "player_to_move": cn.next_player,
            "stones": stones_with_eval,
            "last_move": list(last_move) if last_move else None,
            "prisoner_count": self.game.prisoner_count,
            "analysis": analysis,
            "is_root": cn.is_root,
            "is_pass": cn.is_pass,
            "end_result": self.game.end_result,
            "children": [[c.move.player, list(c.move.coords) if c.move.coords else None] for c in cn.children if c.move],
            "players_info": {
                bw: {
                    "player_type": p.player_type,
                    "player_subtype": p.player_subtype,
                    "name": p.name,
                    "calculated_rank": p.calculated_rank
                }
                for bw, p in self.players_info.items()
            },
            "play_analyze_mode": self.play_analyze_mode,
            "pondering": self.pondering,
        }

    def _do_new_game(self, move_tree=None, analyze_fast=False, sgf_filename=None, size=None, handicap=None, komi=None):
        if self.engine:
            self.engine.on_new_game()
        
        game_properties = {}
        if size:
            game_properties["SZ"] = size
        if handicap is not None:
            game_properties["HA"] = handicap
        if komi is not None:
            game_properties["KM"] = komi

        self.game = Game(
            self,
            self.engine,
            move_tree=move_tree,
            analyze_fast=analyze_fast or not move_tree,
            sgf_filename=sgf_filename,
            game_properties=game_properties
        )
        # Update player info based on game settings
        for bw, player_info in self.players_info.items():
            player_info.sgf_rank = self.game.root.get_property(bw + "R")
            player_info.calculated_rank = None
            self.update_player(bw, player_type=player_info.player_type, player_subtype=player_info.player_subtype)
        
        self.update_state()

    def update_state(self, **_kwargs):
        """Called when the game state changes."""
        self._do_update_state()
        if self.update_state_callback:
            self.update_state_callback(self.get_state())

    def _do_update_state(self):
        if not self.game or not self.game.current_node:
            return
        cn = self.game.current_node
        if self.play_analyze_mode == MODE_PLAY:
            next_player = self.players_info[cn.next_player]
            if cn.analysis_complete and next_player.ai and not cn.children and not self.game.end_result:
                self._do_ai_move(cn)

        if self.engine:
            if getattr(self, "pondering", False):
                self.game.analyze_extra("ponder")
            else:
                self.engine.stop_pondering()

    def __call__(self, message, *args, **kwargs):
        """
        Mimics the message loop dispatch mechanism of KaTrainGui.
        Since we are in a web server (threaded/async), we might execute directly 
        or offload to a background task. For simplicity, we execute directly for now,
        but thread safety is a concern if multiple requests come in.
        """
        # Map message strings to methods, e.g. "undo" -> self._do_undo
        method_name = f"_do_{message.replace('-', '_')}"
        if hasattr(self, method_name):
            getattr(self, method_name)(*args, **kwargs)
            if message != "update_state":
                self.update_state()
        else:
            self.log(f"Unknown action: {message}", OUTPUT_ERROR)

    # --- Helper methods ---
    def _find_node_by_id(self, node_id):
        if not self.game or not self.game.root:
            return None
        to_process = [self.game.root]
        while to_process:
            node = to_process.pop()
            if id(node) == node_id:
                return node
            to_process.extend(node.children)
        return None

    # --- Minimal implementations of _do_* methods needed for core functionality ---

    def _do_nav(self, node_id):
        node = self._find_node_by_id(node_id)
        if node:
            self.game.set_current_node(node)
        else:
            self.log(f"Node not found: {node_id}", OUTPUT_ERROR)

    def _do_load_sgf(self, content):
        from katrain.core.game import KaTrainSGF
        try:
            move_tree = KaTrainSGF.parse_sgf(content)
            self._do_new_game(move_tree=move_tree)
        except Exception as e:
            self.log(f"Failed to load SGF: {e}", OUTPUT_ERROR)

    def _do_update_player(self, bw, player_type=None, player_subtype=None):
        self.update_player(bw, player_type=player_type, player_subtype=player_subtype)

    def _do_ai_move(self, node=None):
        if node is None or self.game.current_node == node:
            mode = self.next_player_info.strategy
            settings = self.config(f"ai/{mode}")
            if settings is not None:
                from katrain.core.ai import generate_ai_move
                generate_ai_move(self.game, mode, settings)
            else:
                self.log(f"AI Mode {mode} not found!", OUTPUT_ERROR)

    def _do_play(self, coords):
        from katrain.core.game import IllegalMoveException, Move
        try:
            self.game.play(Move(coords, player=self.next_player_info.player))
        except IllegalMoveException as e:
            self.log(f"Illegal Move: {e}", OUTPUT_ERROR)

    def _do_undo(self, n_times=1):
        if n_times == "smart":
            n_times = 1
            if self.play_analyze_mode == MODE_PLAY and self.last_player_info.ai and self.next_player_info.human:
                n_times = 2
        self.game.undo(n_times)

    def _do_redo(self, n_times=1):
        self.game.redo(n_times)

    def _do_rotate(self):
        # Rotation is primarily a UI concern, but we can store it or just trigger state update
        self.update_state()

    def _do_find_mistake(self, fn="redo"):
        threshold = self.config("trainer/eval_thresholds")[-4]
        getattr(self.game, fn)(9999, stop_on_mistake=threshold)

    def _do_switch_branch(self, direction):
        # In Kivy, this is in MoveTree
        cn = self.game.current_node
        if cn.parent:
            siblings = cn.parent.ordered_children
            idx = siblings.index(cn)
            new_idx = (idx + direction) % len(siblings)
            self.game.set_current_node(siblings[new_idx])

    def _do_tsumego_frame(self, ko=False, margin=None):
        from katrain.core.tsumego_frame import tsumego_frame_from_katrain_game
        if not self.game.stones:
            return
        black_to_play_p = self.next_player_info.player == "B"
        node, analysis_region = tsumego_frame_from_katrain_game(
            self.game, self.game.komi, black_to_play_p, ko_p=ko, margin=margin
        )
        self.game.set_current_node(node)
        self.play_analyze_mode = MODE_ANALYZE
        if analysis_region:
            flattened_region = [
                analysis_region[0][1],
                analysis_region[0][0],
                analysis_region[1][1],
                analysis_region[1][0],
            ]
            self.game.set_region_of_interest(flattened_region)
        node.analyze(self.game.engines[node.next_player])

    def _do_selfplay_setup(self, until_move, target_b_advantage=None):
        self.game.selfplay(int(until_move) if isinstance(until_move, float) else until_move, target_b_advantage)

    def _do_select_box(self, coords):
        # coords should be [xmin, xmax, ymin, ymax]
        self.game.set_region_of_interest(coords)

    def _do_reset_analysis(self):
        self.game.reset_current_analysis()

    def _do_resign(self):
        self.game.current_node.end_state = f"{self.game.current_node.player}+R"

    def _do_engine_recovery_popup(self, error_message, code):
        self.log(f"Engine Error: {error_message} (Code: {code})", OUTPUT_ERROR)
        # In web context, push error notification to client

    def update_config(self, setting, value):
        if "/" in setting:
            cat, key = setting.split("/")
            if cat not in self._config:
                self._config[cat] = {}
            self._config[cat][key] = value
        else:
            self._config[setting] = value

    def shutdown(self):
        if self.engine:
            try:
                self.engine.shutdown(finish=False)
            except Exception:
                pass
            self.engine = None

    def get_sgf(self):
        if not self.game or not self.game.root:
            return ""
        trainer_config = self.config("trainer", {})
        return self.game.root.sgf(
            save_comments_player={"B": True, "W": True},
            save_comments_class=trainer_config.get("save_feedback", False),
            eval_thresholds=trainer_config.get("eval_thresholds", [12, 6, 3, 1.5, 0.5, 0]),
            save_analysis=trainer_config.get("save_analysis", False),
            save_marks=trainer_config.get("save_marks", False),
        )
