"""Rebuildable kifu search data, deliberately outside business Base.metadata.

Only the explicit migration command creates these tables. They are never part of
business images, approvals, publication receipts, or undo journals.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)

POLICY_VERSION = 1
NAME_LANGUAGES = ("cn", "tw", "jp", "ko", "en")
metadata = MetaData()

state = Table(
    "kifu_search_prepared_state",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("policy_version", Integer, nullable=False, server_default="1"),
    Column("policy_signature", Text, nullable=False, server_default=""),
    Column("enabled", Boolean, nullable=False, server_default=false()),
    Column("ready", Boolean, nullable=False, server_default=false()),
    Column("initial_coverage_complete", Boolean, nullable=False, server_default=false()),
    Column("prepared_at", DateTime(timezone=True)),
    Column("phase", Text, nullable=False, server_default="unprepared"),
    Column("cursor", JSON(none_as_null=True)),
    CheckConstraint("id = 1", name="ck_kifu_prepared_state_singleton"),
)

names = Table(
    "kifu_search_prepared_names",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name_kind", Text, nullable=False),
    Column("source_key", Text, nullable=False),
    Column("source_name_id", Integer),
    Column("lang", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("normalized_term", Text, nullable=False),
    Column("match_class", Text, nullable=False),
    Column("owner_id", Integer),
    Column("eligible", Boolean, nullable=False, server_default=false()),
    Column("exact_group_authorized_ids", JSON, nullable=False, server_default=text("'[]'")),
    Column("semantic", JSON, nullable=False, server_default=text("'{}'")),
    Column("valid", Boolean, nullable=False, server_default=false()),
    Column("policy_version", Integer, nullable=False),
    UniqueConstraint("name_kind", "source_key", "lang", "match_class", name="uq_kifu_prepared_name_source"),
)
Index("ix_kifu_prepared_names_exact", names.c.display_name, names.c.name_kind, names.c.eligible)
Index("ix_kifu_prepared_names_lower", func.lower(names.c.display_name), names.c.name_kind, names.c.eligible)
Index("ix_kifu_prepared_names_token", names.c.name_kind, names.c.lang, names.c.normalized_term)
Index("ix_kifu_prepared_names_owner", names.c.name_kind, names.c.owner_id)

members = Table(
    "kifu_search_prepared_members",
    metadata,
    Column("prepared_name_id", Integer, ForeignKey(names.c.id, ondelete="CASCADE"), primary_key=True),
    Column("album_id", Integer, primary_key=True),
    Column("slot", Text, primary_key=True),
    Column("event_id", Integer),
    Column("selection_id", Integer),
    Column("semantic", JSON, nullable=False, server_default=text("'{}'")),
    CheckConstraint("slot IN ('black','white','event','selected_event')", name="ck_kifu_prepared_member_slot"),
)
Index("ix_kifu_prepared_members_album", members.c.album_id, members.c.prepared_name_id)

displays = Table(
    "kifu_search_prepared_displays",
    metadata,
    Column("album_id", Integer, primary_key=True),
    Column("name_lang", Text, primary_key=True),
    Column("valid", Boolean, nullable=False, server_default=false()),
    Column("policy_version", Integer, nullable=False),
    Column("player_black", Text, nullable=False),
    Column("player_white", Text, nullable=False),
    Column("event", Text, nullable=True),
    Column("black_name_source", JSON(none_as_null=True)),
    Column("white_name_source", JSON(none_as_null=True)),
    Column("event_name_source", JSON(none_as_null=True)),
    Column("obscured", Boolean, nullable=False, server_default=false()),
    Column("selection_id", Integer),
    Column("strict_outputs", JSON, nullable=False, server_default=text("'{}'")),
    CheckConstraint("name_lang IN ('cn','tw','jp','ko','en')", name="ck_kifu_prepared_display_lang"),
)

dependencies = Table(
    "kifu_search_prepared_dependencies",
    metadata,
    Column("target_kind", Text, primary_key=True),
    Column("target_key", Text, primary_key=True),
    Column("input_kind", Text, primary_key=True),
    Column("input_key", Text, primary_key=True),
)
Index(
    "ix_kifu_prepared_dependencies_input",
    dependencies.c.input_kind,
    dependencies.c.input_key,
    dependencies.c.target_kind,
    dependencies.c.target_key,
)

dirty = Table(
    "kifu_search_prepared_dirty",
    metadata,
    Column("input_kind", Text, primary_key=True),
    Column("input_key", Text, primary_key=True),
    Column("reason", Text, nullable=False),
    Column("first_changed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    # Raw OLD/NEW name text is essential: PostgreSQL lower != Python NFKC/casefold.
    # First OLD and latest NEW survive de-duplication; no artifact/SGF is copied.
    Column("old_values", JSON(none_as_null=True)),
    Column("new_values", JSON(none_as_null=True)),
)
