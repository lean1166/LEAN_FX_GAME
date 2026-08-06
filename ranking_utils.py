"""
Utilidades compartidas de ranking entre main.py, window_ranking.py y window_streamer.py.
"""
from database import get_top_players


def load_top_viewers(limit=5):
    """Top viewers por balance, excluyendo al streamer (via get_top_players)."""
    players = get_top_players(limit)
    return [
        {
            "name": p["username"],
            "balance": p["balance"],
            "wins": p["wins"],
            "losses": p["losses"],
        }
        for p in players
    ]


def compute_streak(results):
    """Racha de wins consecutivos. results: WIN/LOSS, más reciente primero."""
    streak = 0
    for result in results:
        if result == "WIN":
            streak += 1
        else:
            break
    return streak
