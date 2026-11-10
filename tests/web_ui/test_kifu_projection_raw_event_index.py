"""Batch-local candidate indexing preserves the existing raw-event proof mapper."""

from collections import Counter
from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from katrain.web.core.models_db import Base, KifuAlbum
from katrain.web.kifu import identity, search_projection as projection


def indexed():
    assert hasattr(projection, "_raw_event_record_index"), "batch-local raw-event record index is missing"
    assert hasattr(projection, "_indexed_raw_event_map"), "projection must reuse the unchanged identity mapper"
    return projection._raw_event_record_index, projection._indexed_raw_event_map


def record(ident, raw, event_id=None, **flags):
    return SimpleNamespace(
        id=ident,
        event=raw,
        event_id=event_id,
        duplicate_of_id=flags.get("duplicate_of_id"),
        list_hidden_reason=flags.get("list_hidden_reason"),
    )


def name(ident, raw, kind, proof, lang="cn"):
    return (
        SimpleNamespace(
            id=ident,
            raw_event_id=ident,
            lang=lang,
            decision_kind=kind,
            evidence_id=1000 + ident,
            display_name=f"label {ident}",
            generation_rule_version="test-v1",
        ),
        raw,
        proof,
    )


def slot(ident, kind="event", event_id=None, **flags):
    return dict(
        album_id=ident,
        slot=kind,
        event_id=event_id,
        approved=flags.get("approved", True),
        duplicate_of_id=flags.get("duplicate_of_id"),
        list_hidden_reason=flags.get("list_hidden_reason"),
    )


def proof_matrix():
    records = [
        record(1, "A"),
        record(2, "A", 17),
        record(3, "A"),
        record(4, "B"),
        record(5, "A", duplicate_of_id=99),
        record(6, "A", list_hidden_reason="review"),
        record(7, None),
        record(8, ""),
        record(9, "C", 17),
        record(10, "D"),
        record(11, "A"),
        record(12, "B", 17),
    ]
    records.append(records[1])  # Repeated input records retain their original order.
    first = dict(
        first_pass=[
            slot(1),
            slot(2, event_id=17),
            slot(3, "selected_event", 17),
            slot(5, duplicate_of_id=99),
            slot(6, list_hidden_reason="review"),
            slot(11),
        ]
    )
    selected = dict(first_pass=[slot(3, "selected_event", 17), slot(4, approved=False), slot(12, "selected_event", 17)])
    rows = [
        name(101, "A", "generated", first),
        name(102, "A", "generated", first),
        name(103, "A", "translated", None),
        name(104, "A", "translated", dict(linked_literal=[dict(id=2, event_id=17)])),
        name(105, "A", "conventional", None),
        name(106, "A", "conventional", None),
        name(107, "D", "archive_description", dict(declaration=dict(occurrence_album_ids=[10]))),
        name(
            108,
            "C",
            "composed",
            dict(
                dependencies=dict(series_event_id=17),
                scope=dict(content=dict(raws=[dict(raw_value="C", occurrence_album_ids=[9])])),
            ),
        ),
        name(109, "B", "generated", {**selected, "record_label": True}),
        name(110, None, "conventional", None),
        name(111, "", "conventional", None),
        name(112, "absent", "conventional", None),
    ]
    return records, rows, {3: ("B", 17), 12: ("B", 17)}, {11}, {(2, "A", 17)}


def test_index_keeps_original_order_duplicates_and_exact_literals():
    build, _ = indexed()
    records, _, selected, _, _ = proof_matrix()
    index = build(records, selected)
    assert [record.id for record in index["A"]] == [1, 2, 3, 5, 6, 11, 2]
    assert [record.id for record in index["B"]] == [3, 4, 12]
    assert [record.id for record in index[None]] == [7]
    assert [record.id for record in index[""]] == [8]


@pytest.mark.parametrize("approvals", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_all_existing_proof_branches_and_row_precedence_are_identical(approvals, reverse):
    build, apply = indexed()
    records, rows, selected, selected_ids, linked = proof_matrix()
    if reverse:
        rows.reverse()
    kwargs = dict(approvals=approvals, selected_ids=selected_ids, linked_members=linked)
    expected = identity._raw_event_map(rows, records, selected, **kwargs)
    actual = apply(rows, build(records, selected), selected, **kwargs)
    assert list(actual.items()) == list(expected.items())
    assert "absent" in actual  # Unscoped rows must run even with no matching records.
    assert actual[None] != actual[""]
    assert (5, "A", None) not in actual and (6, "A", None) not in actual
    assert (11, "A", None) not in actual and (4, "B", None) not in actual
    if not reverse:
        assert actual[(3, "B", 17)] == (("record_label", 1109) if approvals else "label 109")
        assert actual[(2, "A", 17)] == (("translated", 1104) if approvals else "label 104")


def test_complete_projection_and_classification_match_with_linear_candidate_visits(tmp_path, monkeypatch):
    build, _ = indexed()
    engine = create_engine(f'sqlite:///{tmp_path / "projection.db"}')
    Base.metadata.create_all(engine)
    visits = Counter()

    class Counted(list):
        def __init__(self, values, label):
            super().__init__(values)
            self.label = label

        def __iter__(self):
            for value in super().__iter__():
                visits[self.label] += 1
                yield value

    try:
        with Session(engine) as db:
            db.add_all(
                [
                    KifuAlbum(
                        player_black="Black",
                        player_white="White",
                        event=f"Raw {i}",
                        sgf_content="(;)",
                        source_path=f"fixture-{i}.sgf",
                    )
                    for i in range(80)
                ]
            )
            db.commit()
            records = db.query(KifuAlbum).order_by(KifuAlbum.id).all()
            records.append(records[1])
            selected = {records[0].id: (records[1].event, None)}
            rows = [
                name(i, record.event, "generated", dict(first_pass=[slot(record.id)]))
                for i, record in enumerate(records[:-1], 1)
            ]
            rows[1][2]["first_pass"].append(slot(records[0].id, "selected_event"))
            rows.extend(
                [name(1000, records[0].event, "conventional", None), name(1001, records[0].event, "conventional", None)]
            )
            context = projection.ProjectionContext(
                db, True, [], [], [], rows, {}, {}, {}, {}, {}, {}, dict(projected_albums=0)
            )
            context._classification_docs = projection._classification_documents(context)
            classifications = deepcopy(context.classification_documents())
            assert classifications
            monkeypatch.setattr(identity, "live_event_selections", lambda *_: selected)

            def original_candidates(albums, _selected):
                full = Counted(albums, "cartesian")
                return {row[1]: full for row in rows}

            monkeypatch.setattr(projection, "_raw_event_record_index", original_candidates)
            expected = projection.project_album_batch(context, records)
            assert context.classification_documents() == classifications

            def indexed_candidates(albums, selections):
                return {raw: Counted(values, "indexed") for raw, values in build(albums, selections).items()}

            monkeypatch.setattr(projection, "_raw_event_record_index", indexed_candidates)
            context.stats["projected_albums"] = 0
            actual = projection.project_album_batch(context, records)
            assert actual == expected and len(actual) == len(records)
            assert context.classification_documents() == classifications
            assert context.stats["projected_albums"] == len(records)
            first = actual[0]["_source"]
            assert first["raw_event_name_ids"] == [1000, 1001]
            assert first["selected_event_name_ids"] == [rows[1][0].id]
            assert first["display"]["cn"]["event"] == rows[1][0].display_name
            assert visits["cartesian"] > len(records) * len(rows)
            assert visits["indexed"] <= 6 * len(records)
            print(dict(records=len(records), names=len(rows), candidate_visits=dict(visits)))
    finally:
        engine.dispose()
