from typing import Tuple

# Mapping of rank strings to internal float values
# 20k -> -19.0, 1k -> 0.0, 1d -> 1.0, 9d -> 9.0
def rank_to_float(rank_str: str) -> float:
    rank_str = rank_str.lower()
    if 'k' in rank_str:
        num = int(rank_str.replace('k', ''))
        return float(1 - num)
    if 'd' in rank_str:
        num = int(rank_str.replace('d', ''))
        return float(num)
    return -19.0 # Default

def float_to_rank(rank_val: float) -> str:
    if rank_val >= 0.5:
        return f"{int(round(rank_val))}d"
    else:
        return f"{int(round(1 - rank_val))}k"

def get_elo_per_level(rank_val: float) -> int:
    # 5k is -4.0
    if rank_val < -4.0: # Below 5k
        return 80
    if rank_val <= 9.0: # 5k to 9d
        return 100
    return 300 # Above 9d

def get_win_threshold(rank_val: float) -> int:
    # "净胜2至6盘一升降" - let's use a dynamic threshold or fixed for now
    # For MVP, let's use 3.
    return 3

def calculate_rank_update(current_rank: str, current_net_wins: int, current_elo: int, won: bool) -> Tuple[str, int, int, int]:
    """
    Returns: (new_rank, new_net_wins, new_elo, elo_change)
    """
    rank_val = rank_to_float(current_rank)
    win_inc = 1 if won else -1
    new_net_wins = current_net_wins + win_inc
    
    threshold = get_win_threshold(rank_val)
    elo_per_level = get_elo_per_level(rank_val)
    
    # Base Elo change for a single game
    # If 3 games = 1 level, then 1 game = elo_per_level / 3
    base_elo_change = elo_per_level // threshold
    elo_change = base_elo_change if won else -base_elo_change
    
    new_elo = current_elo + elo_change
    new_rank_val = rank_val
    
    if new_net_wins >= threshold:
        new_rank_val += 1.0
        new_net_wins = 0
    elif new_net_wins <= -threshold:
        new_rank_val -= 1.0
        new_net_wins = 0
        
    # Boundary checks
    if new_rank_val < -19.0: new_rank_val = -19.0
    if new_rank_val > 12.0: new_rank_val = 12.0 # Max 12d?
    
    return float_to_rank(new_rank_val), new_net_wins, new_elo, elo_change
