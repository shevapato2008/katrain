"""Prepare the kifu catalog schema before starting a new Web release.

Run once on each cloud database before the new Web image starts. PostgreSQL
indexes are built concurrently here, never inside Web startup. ``--validate``
performs the separate foreign-key scan after the service migration succeeds.
"""

import argparse

from katrain.web.core.db import Base, engine
from katrain.web.core.migrations import (
    create_kifu_album_identity_indexes,
    migrate_kifu_catalog_schema,
    validate_kifu_album_foreign_keys,
)
from katrain.web.core.models_db import (
    KifuAlbumSource,
    KifuDedupBatch,
    KifuDedupChange,
    KifuEvent,
    KifuEventAlias,
    KifuEventName,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuSource,
)


CATALOG_TABLES = [
    model.__table__
    for model in (
        KifuPlayer,
        KifuEvent,
        KifuPlayerAlias,
        KifuEventAlias,
        KifuPlayerName,
        KifuEventName,
        KifuSource,
        KifuAlbumSource,
        KifuDedupBatch,
        KifuDedupChange,
    )
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", action="store_true", help="also validate existing album foreign-key rows")
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine, tables=CATALOG_TABLES)
    migrate_kifu_catalog_schema(engine)
    create_kifu_album_identity_indexes(engine)
    if args.validate:
        validate_kifu_album_foreign_keys(engine)
    print("Kifu catalog schema ready" + ("; foreign keys validated" if args.validate else ""))


if __name__ == "__main__":
    main()
