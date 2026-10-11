"""Report live kifu identity-preprocessing progress without changing data."""

import json
import os

from sqlalchemy import create_engine, text


def progress(database_url: str) -> dict:
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            albums = conn.execute(text("""
                SELECT count(*) AS games,
                       count(black_player_id) + count(white_player_id) AS player_slots_linked,
                       count(event_id) AS event_games_linked,
                       count(event_edition_id) AS edition_games_linked,
                       count(*) FILTER (WHERE black_player_id IS NOT NULL
                                        AND white_player_id IS NOT NULL
                                        AND event_id IS NOT NULL) AS fully_linked_games
                FROM kifu_albums
            """)).mappings().one()
            players = conn.scalar(text("SELECT count(*) FROM kifu_players"))
            events = conn.scalar(text("SELECT count(*) FROM kifu_events"))
            editions = conn.scalar(text("SELECT count(*) FROM kifu_event_editions"))
            raw_players = conn.scalar(text("SELECT count(*) FROM kifu_raw_player_values"))
            raw_events = conn.scalar(text("SELECT count(*) FROM kifu_raw_event_values"))
    finally:
        engine.dispose()
    games = albums["games"]
    return {
        "games": games,
        "player_slots": games * 2,
        "player_slots_linked": albums["player_slots_linked"],
        "player_slots_linked_pct": round(100 * albums["player_slots_linked"] / (games * 2), 2) if games else 0,
        "event_games_linked": albums["event_games_linked"],
        "event_games_linked_pct": round(100 * albums["event_games_linked"] / games, 2) if games else 0,
        "edition_games_linked": albums["edition_games_linked"],
        "fully_linked_games": albums["fully_linked_games"],
        "fully_linked_games_pct": round(100 * albums["fully_linked_games"] / games, 2) if games else 0,
        "player_ids": players,
        "event_type_ids": events,
        "event_edition_ids": editions,
        "raw_player_spellings": raw_players,
        "raw_event_values": raw_events,
    }


if __name__ == "__main__":
    print(json.dumps(progress(os.environ["KATRAIN_DATABASE_URL"]), ensure_ascii=False, sort_keys=True))
