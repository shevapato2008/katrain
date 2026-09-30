"""SQLite development databases must enforce declared kifu foreign keys."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from katrain.web.core.db import enable_sqlite_foreign_keys
from katrain.web.core.models_db import Base


def test_sqlite_rejects_orphan_kifu_player_reference():
    engine = create_engine("sqlite:///:memory:")
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO kifu_albums (player_black, player_white, sgf_content, source_path, black_player_id) "
                    "VALUES ('A', 'B', '(;B[pd])', 'orphan.sgf', 999)"
                )
            )
    engine.dispose()
