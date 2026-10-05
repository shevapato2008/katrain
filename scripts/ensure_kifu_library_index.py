#!/usr/bin/env python3
"""Create the bounded-library count index online; does not block album writes."""
import os

from sqlalchemy import create_engine, inspect, text


def main():
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"])
    if engine.dialect.name != "postgresql":
        raise SystemExit("This online migration is for PostgreSQL only")
    columns = {column["name"] for column in inspect(engine).get_columns("kifu_albums")}
    visible = "duplicate_of_id IS NULL"
    if "list_hidden_reason" in columns:
        visible += " AND list_hidden_reason IS NULL"
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(
            text(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_kifu_library_visible_id "
                f"ON kifu_albums (id) WHERE {visible}"
            )
        )
        connection.execute(text("ANALYZE kifu_albums"))
        for row in connection.execute(
            text(f"EXPLAIN (ANALYZE, BUFFERS) SELECT count(id) FROM kifu_albums WHERE {visible}")
        ):
            print(row[0])


if __name__ == "__main__":
    main()
