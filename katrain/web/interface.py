import logging
import time
import threading
import copy
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
    PRIORITY_DEFAULT,
    PRIORITY_GAME_ANALYSIS,
)
from katrain.core.engine import create_engine
from katrain.core.game import Game
from katrain.core.lang import i18n
from katrain.gui.theme import Theme

# Configure standard logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("katrain_web")


class NullEngine:
    def __init__(self):
        self.config = {"max_visits": 10, "fast_visits": 5}

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


class MockMoveTree:
    def __init__(self):
        self.insert_node = None

    def redraw(self):
        pass

    def redraw_tree_trigger(self):
        pass


class MockControls:
    def __init__(self, katrain):
        self.katrain = katrain
        self.move_tree = MockMoveTree()

    def set_status(self, message, level=OUTPUT_INFO, **_kwargs):
        self.katrain.log(message, level)


class WebGame(Game):
    def set_current_node(self, node):
        # Update timer for the *previous* node/player before switching
        if self.katrain and hasattr(self.katrain, "update_timer"):
            self.katrain.update_timer()
        
        super().set_current_node(node)
        
        # Reset timer baseline for the *new* node/player
        if self.katrain and hasattr(self.katrain, "last_timer_update"):
            self.katrain.last_timer_update = time.time()

    def play(self, move, ignore_ko=False, analyze=True):
        # Update timer for the *previous* node/player before switching
        if self.katrain and hasattr(self.katrain, "update_timer"):
            self.katrain.update_timer()

        node = super().play(move, ignore_ko=ignore_ko, analyze=analyze)

        # Reset timer baseline for the *new* node/player
        if self.katrain and hasattr(self.katrain, "last_timer_update"):
            self.katrain.last_timer_update = time.time()
        
        return node


class WebKaTrain(KaTrainBase):
    """
    A headless version of KaTrain for the Web UI.
    """

    def __init__(self, force_package_config=False, debug_level=None, enable_engine=True, user_id=None, **kwargs):
        # Initialize attributes used in log() before super().__init__
        self.message_callback: Optional[Callable] = None
        self.enable_engine = enable_engine
        self.user_id = user_id
        self.ai_lock = threading.Lock()

        # Initialize base without invoking Kivy-specifics that might break headless if possible.
        # KaTrainBase __init__ is relatively safe, mostly config and logging.
        super().__init__(force_package_config, debug_level, **kwargs)

        try:
            from kivymd.app import MDApp
            MDApp.gui = self
        except Exception:
            pass

        self.engine = None
        self.update_state_callback: Optional[Callable] = None
        self.controls = MockControls(self)
        self.play_analyze_mode = MODE_PLAY
        self.pondering = False
        self.timer_paused = True
        self.last_timer_update = time.time()
        self.main_time_used_by_player = {"B": 0, "W": 0}
        self.show_children = False
        self.show_dots = False
        self.show_hints = False
        self.show_policy = False
        self.show_ownership = False
        self.show_move_numbers = False
        self.show_coordinates = True
        self.zen_mode = False
        self.preview_pv = []
        self.active_game_timer = self.config("timer")

        # Initialize language from config
        from katrain.web.core.config import settings
        lang = self.config("general/lang") or self.config("general/language") or settings.DEFAULT_LANG
        
        # Force update default language if config is 'en' but system default is set to something else (e.g. 'cn')
        # This fixes the issue where existing user configs with 'en' prevent the new default from applying
        if lang == 'en' and settings.DEFAULT_LANG != 'en':
            self.log(f"Updating default language from 'en' to '{settings.DEFAULT_LANG}'", OUTPUT_INFO)
            lang = settings.DEFAULT_LANG
        
        # Actually switch the global i18n context to this instance's language
        i18n.switch_lang(lang)

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
        if isinstance(message, dict):
            # Avoid dumping raw analysis JSON to the status bar
            if "moveInfos" in message or "rootInfo" in message:
                return
            message = str(message)
        else:
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

        self.update_timer()
        cn = self.game.current_node
        last_move = cn.move.coords if cn.move else None

        # Get history: full main line from root, with current node's position marked
        # 1. Walk from current node to root to get the path up
        path_to_root = []
        node = cn
        while node:
            path_to_root.append(node)
            node = node.parent
        path_to_root.reverse()

        # 2. Continue from current node down the main line (first child)
        continuation = []
        node = cn.children[0] if cn.children else None
        while node:
            continuation.append(node)
            node = node.children[0] if node.children else None

        # 3. Full main line = path_to_root + continuation
        nodes = path_to_root + continuation
        current_node_index = len(path_to_root) - 1

        history = []
        for node in nodes:
            history.append({
                "node_id": id(node),
                "score": node.score if node.analysis_exists else None,
                "winrate": node.winrate if node.analysis_exists else None,
            })

        # Format stones with evaluation and move numbers
        stones_with_eval = []
        # To get evaluation and move number for each stone, we map coordinates to nodes in path to current.
        coord_to_info = {}
        for idx, h_node in enumerate(path_to_root):
            if h_node.move and h_node.move.coords:
                coord_to_info[h_node.move.coords] = {"score_loss": h_node.points_lost, "move_number": idx}

        for move in self.game.stones:
            player, coords = move.player, move.coords
            info = coord_to_info.get(tuple(coords), {})
            score_loss = info.get("score_loss")
            move_number = info.get("move_number")
            stones_with_eval.append([player, list(coords) if coords else None, score_loss, move_number])

        # Format analysis data for the frontend
        analysis = None
        if cn.analysis and cn.analysis.get("root"):
            root = cn.analysis["root"]
            moves = []
            from katrain.core.sgf_parser import Move
            # Use candidate_moves which contains calculated pointsLost and accurate metrics
            for move_info in cn.candidate_moves:
                gtp = move_info["move"]
                try:
                    m = Move.from_gtp(gtp)
                    moves.append({
                        **move_info,
                        "move": gtp,
                        "coords": list(m.coords) if m.coords else None,
                        "scoreLoss": move_info.get("pointsLost", 0),
                        "winrate": move_info.get("winrate", 0),
                        "visits": move_info.get("visits", 0),
                    })
                except Exception:
                    pass
            # Sort moves by visits descending (standard KaTrain behavior)
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
            "note": cn.note,
            "commentary": cn.comment(details=self.play_analyze_mode == MODE_ANALYZE or not self.config("trainer/lock_ai"), interactive=True),
            "analysis": analysis,
            "is_root": cn.is_root,
            "is_pass": cn.is_pass,
            "end_result": self.game.end_result,
            "children": [[c.move.player, list(c.move.coords) if c.move.coords else None] for c in cn.children if c.move],
            "ghost_stones": [[c.move.player, list(c.move.coords) if c.move.coords else None] for c in cn.children if c.move] + self.preview_pv,
            "players_info": {
                bw: {
                    "player_type": p.player_type,
                    "player_subtype": p.player_subtype,
                    "name": p.name,
                    "calculated_rank": p.calculated_rank,
                    "periods_used": p.periods_used,
                    "main_time_used": self.main_time_used_by_player.get(bw, 0)
                }
                for bw, p in self.players_info.items()
            },
            "play_analyze_mode": self.play_analyze_mode,
            "insert_mode": getattr(self.game, "insert_mode", False),
            "pondering": self.pondering,
            "language": i18n.lang,
            "available_languages": ["cn", "de", "en", "es", "fr", "jp", "ko", "ru", "tr", "tw", "ua"],
            "theme": self.config("trainer/theme"),
            "available_themes": list(Theme.EVAL_COLORS.keys()),
            "eval_colors": Theme.EVAL_COLORS[self.config("trainer/theme")],
            "trainer_settings": {
                **self.config("trainer"),
                "fast_visits": self.config("engine/fast_visits"),
                "max_visits": self.config("engine/max_visits")
            },
            "timer": {
                "paused": self.timer_paused,
                "main_time_used": self.main_time_used_by_player.get(cn.next_player, 0),
                "current_node_time_used": cn.time_used,
                "next_player_periods_used": self.next_player_info.periods_used,
                "settings": self.active_game_timer
            },
            "ui_state": {
                "show_children": self.show_children,
                "show_dots": self.show_dots,
                "show_hints": self.show_hints,
                "show_policy": self.show_policy,
                "show_ownership": self.show_ownership,
                "show_move_numbers": self.show_move_numbers,
                "show_coordinates": self.show_coordinates,
                "zen_mode": self.zen_mode,
            },
            "engine": getattr(self, "last_engine", None)
        }

    def _do_new_game(self, move_tree=None, analyze_fast=False, sgf_filename=None, size=None, handicap=None, komi=None, rules=None, skip_initial_analysis=False):
        if self.engine:
            self.engine.on_new_game()
        
        self.active_game_timer = copy.deepcopy(self.config("timer"))

        # Update global config for persistence of defaults
        if size:
            self.update_config("game/size", size)
        if handicap is not None:
            self.update_config("game/handicap", handicap)
        if komi is not None:
            self.update_config("game/komi", komi)
        if rules:
            self.update_config("game/rules", rules)

        game_properties = {}
        if size:
            game_properties["SZ"] = size
        if handicap is not None: # Note: 0 is falsy, check if not None
            game_properties["HA"] = handicap
        if komi is not None:
            game_properties["KM"] = komi
        if rules:
            game_properties["RU"] = rules

        self.game = WebGame(
            self,
            self.engine,
            move_tree=move_tree,
            analyze_fast=analyze_fast or not move_tree,
            sgf_filename=sgf_filename,
            game_properties=game_properties,
            user_id=self.user_id,
            skip_initial_analysis=skip_initial_analysis,
        )
        
        # Ensure handicap stones are placed if handicap is set
        if handicap and handicap >= 2:
            self.game.root.place_handicap_stones(handicap)

        # Reset timer state for new game
        self.timer_paused = self.config("timer/paused")
        self.last_timer_update = time.time()
        self.main_time_used_by_player = {"B": 0, "W": 0}
        
        # Save names before reset if they were set (e.g. by API call just before this)
        saved_names = {bw: p.name for bw, p in self.players_info.items()}
        self.reset_players() # Resets periods_used
        for bw, name in saved_names.items():
            if name: self.players_info[bw].name = name
        
        # Update player info based on game settings
        for bw, player_info in self.players_info.items():
            player_info.sgf_rank = self.game.root.get_property(bw + "R")
            player_info.calculated_rank = None
            self.update_player(bw, player_type=player_info.player_type, player_subtype=player_info.player_subtype)
        
        self.update_state()

    def _do_edit_game(self, size=None, handicap=None, komi=None, rules=None):
        changed = False
        if size and list(self.game.board_size) != [size, size]:
            self.game.root.set_property("SZ", size)
            self.update_config("game/size", size)
            changed = True
        if handicap is not None and self.game.root.handicap != handicap:
            self.game.root.set_property("HA", handicap)
            self.game.root.place_handicap_stones(handicap)
            self.update_config("game/handicap", handicap)
            changed = True
        if komi is not None and self.game.root.komi != komi:
            self.game.root.set_property("KM", komi)
            self.update_config("game/komi", komi)
            changed = True
        if rules and self.game.root.ruleset != rules:
            self.game.root.set_property("RU", rules)
            self.update_config("game/rules", rules)
            changed = True
        
        if changed:
            if self.engine:
                self.engine.on_new_game()
            self.game.analyze_all_nodes(analyze_fast=True)
            self.update_state()

    def update_state(self, **_kwargs):
        """Called when the game state changes."""
        # 1. Broadcast current state (useful for showing hints/analysis before AI moves)
        if self.update_state_callback:
            self.update_state_callback(self.get_state())
        
        # 2. Handle logic that might change the state (like AI moving)
        self._do_update_state()

    def _do_update_state(self):
        if not self.game or not self.game.current_node:
            return
        cn = self.game.current_node
        if self.play_analyze_mode == MODE_PLAY:
            next_player = self.players_info[cn.next_player]
            teaching_undo = self.config("trainer/teaching") and self.last_player_info.human
            
            if (
                teaching_undo
                and cn.analysis_complete
                and cn.parent 
                and cn.parent.analysis_complete
                and not cn.children
                and not self.game.end_result
            ):
                self.game.analyze_undo(cn)
                cn = self.game.current_node # Re-fetch if undo happened

            if cn.analysis_complete and next_player.ai and not cn.children and not self.game.end_result and not (teaching_undo and cn.auto_undo is None):
                self._do_ai_move(cn)
                # 3. CRITICAL: Broadcast again after AI has placed its stone
                if self.update_state_callback:
                    self.update_state_callback(self.get_state())

        if self.game.end_result and not getattr(self, "_game_end_reported", False):
            self._game_end_reported = True
            sum_stats, histogram, player_ptloss = self._do_game_report()
            self.message_callback("game_report", {
                "sum_stats": sum_stats,
                "histogram": histogram,
                "player_ptloss": player_ptloss,
                "thresholds": self.config("trainer/eval_thresholds"),
                "end_result": self.game.end_result
            })
        elif not self.game.end_result:
            self._game_end_reported = False

        if self.engine:
            if getattr(self, "pondering", False):
                self.game.analyze_extra("ponder")
            else:
                self.engine.stop_pondering()

    def update_timer(self):
        now = time.time()
        dt = now - self.last_timer_update
        self.last_timer_update = now

        if self.timer_paused or self.play_analyze_mode != MODE_PLAY or not self.game:
            return

        cn = self.game.current_node
        if cn.children: # Only count time for the active leaf node
            return

        main_time = self.active_game_timer.get("main_time", 0) * 60
        byo_len = max(1, self.active_game_timer.get("byo_length", 30))
        byo_num = max(1, self.active_game_timer.get("byo_periods", 5))
        
        current_player = self.next_player_info.player
        main_time_used = self.main_time_used_by_player.get(current_player, 0)
        main_time_left = main_time - main_time_used

        if main_time_left > 0:
            used_main = min(dt, main_time_left)
            self.main_time_used_by_player[current_player] = main_time_used + used_main
            dt -= used_main
        
        if dt > 0:
            cn.time_used += dt
            while cn.time_used > byo_len and self.next_player_info.periods_used < byo_num:
                cn.time_used -= byo_len
                self.next_player_info.periods_used += 1

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

    def _do_show_pv(self, pv_str):
        from katrain.core.sgf_parser import Move
        stones = []
        parts = pv_str.split()
        if not parts:
            return
        player = parts[0][0] # First char is player B or W
        first_move_gtp = parts[0][1:]
        
        # Handle cases like "B D4 Q16" or "BD4 Q16"
        if first_move_gtp:
            moves_gtp = [first_move_gtp] + parts[1:]
        else:
            moves_gtp = parts[1:]

        for i, gtp in enumerate(moves_gtp):
            try:
                m = Move.from_gtp(gtp)
                if m.coords:
                    stones.append(["B" if (player == "B") == (i % 2 == 0) else "W", list(m.coords)])
            except Exception:
                pass
        self.preview_pv = stones
        self.update_state()

    def _do_clear_pv(self):
        self.preview_pv = []
        self.update_state()

    def _do_nav(self, node_id):
        node = self._find_node_by_id(node_id)
        if node:
            self.game.set_current_node(node)
            # On-demand analysis: if this node has no analysis yet, trigger deep analysis
            if not node.analysis_exists:
                engine = self.game.engines[node.next_player]
                node.analyze(engine, priority=PRIORITY_DEFAULT, visits=500)
        else:
            self.log(f"Node not found: {node_id}", OUTPUT_ERROR)

    def _do_load_sgf(self, content, skip_initial_analysis=False):
        from katrain.core.game import KaTrainSGF
        try:
            move_tree = KaTrainSGF.parse_sgf(content)
            self._do_new_game(move_tree=move_tree, skip_initial_analysis=skip_initial_analysis)
        except Exception as e:
            self.log(f"Failed to load SGF: {e}", OUTPUT_ERROR)

    def _do_analysis_scan(self, visits=500, batch_size=10):
        """Background scan: analyze all unanalyzed nodes in batches to avoid overwhelming the engine."""
        import threading as _threading

        # Collect main-line nodes that need analysis
        nodes_to_analyze = []
        node = self.game.root
        while node:
            if not node.analysis_exists:
                nodes_to_analyze.append(node)
            node = node.children[0] if node.children else None

        if not nodes_to_analyze:
            return

        def _run_batched_scan():
            for i in range(0, len(nodes_to_analyze), batch_size):
                batch = nodes_to_analyze[i : i + batch_size]
                for n in batch:
                    engine = self.game.engines[n.next_player]
                    n.analyze(engine, priority=PRIORITY_GAME_ANALYSIS, visits=visits)
                # Wait for this batch to complete before sending next
                for _ in range(600):  # up to 60s per batch
                    if all(n.analysis_exists for n in batch):
                        break
                    import time
                    time.sleep(0.1)

        _threading.Thread(target=_run_batched_scan, daemon=True).start()

    def _do_analysis_progress(self):
        """Return analysis progress: how many nodes in the main line have been analyzed."""
        if not self.game:
            return {"analyzed": 0, "total": 0}
        # Count nodes along the main line (root to deepest child following first child)
        total = 0
        analyzed = 0
        node = self.game.root
        while node:
            total += 1
            if node.analysis_exists:
                analyzed += 1
            node = node.children[0] if node.children else None
        return {"analyzed": analyzed, "total": total}

    def _do_swap_players(self):
        self.players_info["B"], self.players_info["W"] = self.players_info["W"], self.players_info["B"]
        self.players_info["B"].player = "B"
        self.players_info["W"].player = "W"
        self.update_state()

    def _do_update_player(self, bw, player_type=None, player_subtype=None, name=None):
        if name is not None:
            self.players_info[bw].name = name
        self.update_player(bw, player_type=player_type, player_subtype=player_subtype)

    def play_stone_sound(self):
        if self.message_callback:
            if self.game.last_capture:
                self.message_callback("sound", {"sound": "capturing"})
            elif not self.game.current_node.is_pass:
                import random
                self.message_callback("sound", {"sound": f"stone{random.randint(1, 5)}"})

    def _do_ai_move(self, node=None):
        with self.ai_lock:
            # Only generate AI move if the next player is actually an AI
            if not self.next_player_info.ai:
                return
            if node is None or self.game.current_node == node:
                mode = self.next_player_info.strategy
                settings = self.config(f"ai/{mode}")
                if settings is not None:
                    from katrain.core.ai import generate_ai_move
                    result = generate_ai_move(self.game, mode, settings)
                    if result is None:
                        # AI resigned, state will be updated by the caller
                        return
                    self.play_stone_sound()
                else:
                    self.log(f"AI Mode {mode} not found!", OUTPUT_ERROR)

    def _do_play(self, coords):
        from katrain.core.game import IllegalMoveException, Move
        from katrain.core.constants import STATUS_TEACHING
        
        self.update_timer()
        game = self.game
        current_node = game and self.game.current_node
        if (
            current_node
            and not current_node.children
            and not self.next_player_info.ai
            and not self.timer_paused
            and self.play_analyze_mode == MODE_PLAY
            and self.active_game_timer.get("main_time", 0) * 60 - self.main_time_used_by_player.get(self.next_player_info.player, 0) <= 0
            and current_node.time_used < self.active_game_timer.get("minimal_use", 0)
        ):
            self.controls.set_status(
                i18n._("move too fast").format(num=self.active_game_timer.get("minimal_use", 0)), STATUS_TEACHING
            )
            return

        try:
            self.game.play(Move(coords, player=self.next_player_info.player))
            self.play_stone_sound()
        except IllegalMoveException as e:
            self.log(f"Illegal Move: {e}", OUTPUT_ERROR)
        finally:
            self.last_timer_update = time.time()

    def _do_undo(self, n_times=1):
        if n_times == "smart":
            n_times = 1
            if self.play_analyze_mode == MODE_PLAY and self.last_player_info.ai and self.next_player_info.human:
                n_times = 2
        self.game.undo(n_times)
        self.update_state()

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

    def _do_delete_node(self, node_id=None):
        node = self._find_node_by_id(node_id) if node_id else self.game.current_node
        if node and node.parent:
            if node.shortcut_from:
                parent = node.shortcut_from
                via = [v for m, v in parent.shortcuts_to if m == node]
                node.remove_shortcut()
                if via:
                    parent.children.remove(via[0])
            else:
                parent = node.parent
                parent.children.remove(node)
            self.game.set_current_node(parent)

    def _do_prune_branch(self, node_id=None):
        node = self._find_node_by_id(node_id) if node_id else self.game.current_node
        if node and node.parent:
            curr = node
            while curr.parent is not None:
                curr.parent.children = [curr]
                curr = curr.parent
            self.game.set_current_node(node)

    def _do_make_main_branch(self, node_id=None):
        node = self._find_node_by_id(node_id) if node_id else self.game.current_node
        if node and node.parent:
            curr = node
            while curr.parent is not None:
                curr.parent.children.remove(curr)
                curr.parent.children.insert(0, curr)
                curr = curr.parent
            self.game.set_current_node(node)

    def _do_toggle_collapse(self, node_id=None):
        node = self._find_node_by_id(node_id) if node_id else self.game.current_node
        if node and node.parent:
            if node.shortcut_from:
                node.remove_shortcut()
            else:
                parent = node.parent
                while len(parent.children) == 1 and not parent.is_root and not parent.shortcut_from:
                    parent = parent.parent
                parent.add_shortcut(node)

    def _do_toggle_ui(self, setting):
        # Map frontend keys to backend attributes
        mapping = {
            "eval": "dots",
            "coords": "coordinates",
            "numbers": "move_numbers"
        }
        key = mapping.get(setting, setting)
        attr = f"show_{key}"
        
        if setting == "zen_mode":
            attr = "zen_mode"
            
        if hasattr(self, attr):
            setattr(self, attr, not getattr(self, attr))

    def _do_switch_lang(self, lang):
        i18n.switch_lang(lang)
        self.update_config("general/language", lang)

    def _do_switch_theme(self, theme):
        self.update_config("trainer/theme", theme)

    def _do_analyze_extra(self, mode, **kwargs):
        self.game.analyze_extra(mode, **kwargs)

    def _do_insert_mode(self, mode="toggle"):
        self.game.set_insert_mode(mode)

    def _do_reset_analysis(self):
        self.game.reset_current_analysis()

    def _do_game_analysis(self, **kwargs):
        self.game.analyze_extra("game", **kwargs)

    def _do_game_report(self, depth_filter=None):
        from katrain.core.ai import game_report
        thresholds = self.config("trainer/eval_thresholds")
        return game_report(self.game, thresholds, depth_filter=depth_filter)

    def _do_resign(self):
        self.game.current_node.end_state = f"{self.game.current_node.player}+R"

    def _do_timeout(self):
        """End game due to timeout - current player loses on time"""
        self.game.current_node.end_state = f"{self.game.current_node.player}+T"

    def _do_engine_recovery_popup(self, error_message, code):
        # Sync global i18n before logging translated strings
        current_lang = self.config("general/language") or self.config("general/lang") or "en"
        i18n.switch_lang(current_lang)
        self.log(f"Engine Error: {error_message} (Code: {code})", OUTPUT_ERROR)
        # In web context, push error notification to client

    def update_config(self, setting, value):
        parts = setting.split("/")
        if len(parts) > 1:
            conf = self._config
            for part in parts[:-1]:
                if part not in conf or not isinstance(conf[part], dict):
                    conf[part] = {}
                conf = conf[part]
            conf[parts[-1]] = value
            cat = parts[0]
        else:
            cat = None
            self._config[setting] = value

        # Handle language change
        if setting == "general/language":
            i18n.switch_lang(value)
            self.update_state()

        if setting == "timer/paused":
            self.timer_paused = value

        if setting.startswith("timer/") and hasattr(self, "active_game_timer"):
            key = setting.split("/")[1]
            if key in self.active_game_timer:
                self.active_game_timer[key] = value

        if setting.startswith("ai/"):
            self.update_calculated_ranks()
            self.update_state()

        # Logic from ConfigPopup.update_config to restart engine if needed
        ignore = {"max_visits", "fast_visits", "max_time", "enable_ownership", "wide_root_noise"}
        if "engine" in setting and not any(ig in setting for ig in ignore):
            self.log(f"Restarting Engine after {setting} settings change")
            if self.engine:
                try:
                    self.engine.shutdown(finish=False)
                except Exception:
                    pass
            self.engine = create_engine(self, self.config("engine"))
            if self.game:
                self.game.engines = {"B": self.engine, "W": self.engine}
                self.game.analyze_all_nodes(analyze_fast=True)
            self.update_state()

        # Persist to ~/.katrain/config.json just like Kivy GUI
        self.save_config(cat)

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
