"""Prepare the kifu catalog schema before starting a new Web release.

Run once on each cloud database before the new Web image starts. PostgreSQL
indexes are built concurrently here, never inside Web startup. ``--validate``
performs the separate foreign-key scan after the service migration succeeds.
"""

import argparse

from katrain.web.core.db import Base, engine
from katrain.web.core.migrations import (
    create_kifu_album_identity_indexes,
    create_kifu_name_indexes,
    install_kifu_name_change_immutability,
    migrate_kifu_catalog_schema,
    migrate_kifu_name_schema,
    validate_kifu_album_foreign_keys,
    validate_kifu_name_foreign_keys,
    verify_kifu_event_selection_schema,
    verify_kifu_name_schema,
)
from katrain.web.core.models_db import (
    KifuAlbumEventSelection,
    KifuAlbumSource,
    KifuDedupBatch,
    KifuDedupChange,
    KifuEvent,
    KifuEventAlias,
    KifuEventName,
    KifuEventSelectionBatch,
    KifuNameBatch,
    KifuNameChange,
    KifuNameResearchEvidence,
    KifuNameSourceRegistry,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuRawEventName,
    KifuRawEventValue,
    KifuRawPlayerName,
    KifuRawPlayerValue,
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
        KifuRawPlayerValue,
        KifuRawEventValue,
        KifuNameSourceRegistry,
        KifuNameResearchEvidence,
        KifuRawPlayerName,
        KifuRawEventName,
        KifuNameBatch,
        KifuNameChange,
        KifuEventSelectionBatch,
        KifuAlbumEventSelection,
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
    migrate_kifu_name_schema(engine)
    verify_kifu_name_schema(engine)
    verify_kifu_event_selection_schema(engine)
    create_kifu_name_indexes(engine)
    install_kifu_name_change_immutability(engine)
    create_kifu_album_identity_indexes(engine)
    if args.validate:
        validate_kifu_album_foreign_keys(engine)
        validate_kifu_name_foreign_keys(engine)
    print("Kifu catalog schema ready" + ("; foreign keys validated" if args.validate else ""))


if __name__ == "__main__":
    main()
