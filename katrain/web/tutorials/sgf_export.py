"""Independent SGFs plus reconstructable JSON; unknown colors remain unknown."""

from katrain.core.sgf_parser import Move, SGFNode
from katrain.web.tutorials.recognition_import import content_sha256
from katrain.web.tutorials.replay import validate_replay


def diagram_extent(payload, *, using_replay):
    """State the exported known rectangles without declaring unseen points empty."""
    size = payload.get("size", 19)
    source = payload.get("source_region") or {}
    source_known = (
        {key: source[key] for key in ("col", "row", "cols", "rows")} if source.get("confirmed") is True else None
    )
    initial = ((payload.get("replay") or {}).get("initial") or {}) if using_replay else {}
    initial_known = initial.get("known_region")
    full_board = {"col": 0, "row": 0, "cols": size, "rows": size}
    outside_source_unknown = source_known != full_board
    outside_initial_unknown = initial_known != full_board if using_replay else None
    return {
        "source_known_region": source_known,
        "outside_source_region_unknown": outside_source_unknown,
        "initial_known_region": initial_known,
        "outside_initial_known_region_unknown": outside_initial_unknown,
        "unknown_extent": outside_source_unknown or bool(outside_initial_unknown),
    }


def diagram_sgf(payload, *, metadata):
    size = payload.get("size", 19)
    proof = validate_replay(payload)
    replay = payload.get("replay")
    complete = proof["status"] == "complete"
    initial = replay["initial"] if complete else payload
    extent = diagram_extent(payload, using_replay=complete)
    comment = [
        f"Tutorial figure {metadata['figure_id']}; version={metadata['version_kind']}",
        f"payload_sha256={content_sha256(payload)}",
        f"replay={proof['status']}",
        f"source={metadata.get('source', [])}",
        f"review={metadata.get('review', {})}",
        f"source_region={payload.get('source_region')}",
        f"known_region={extent['source_known_region']}",
        f"outside_known_region={'unknown' if extent['outside_source_region_unknown'] else 'known'}",
        f"unknown_extent={extent['unknown_extent']}",
        f"inference={metadata.get('inference', False)}; uncertainty={metadata.get('uncertainty', False)}",
    ]
    if complete:
        comment.append(f"initial_known_region={extent['initial_known_region']}")
        comment.append(
            f"outside_initial_known_region={'unknown' if extent['outside_initial_known_region_unknown'] else 'known'}"
        )
    unknown = [
        stone if isinstance(stone, dict) else {"point": stone, "color": None}
        for stone in payload.get("unknown_stones") or []
    ]
    if unknown:
        comment.append(
            "Unknown occupied coordinates (not AB/AW): "
            + "; ".join(f"{s['point'][0]},{s['point'][1]} {s.get('evidence', '')}" for s in unknown)
        )
    if proof["issues"]:
        comment.append("Replay pending: " + "; ".join(proof["issues"]))
    if metadata.get("evidence"):
        import json

        comment.append(
            "Original recognition evidence: " + json.dumps(metadata["evidence"], ensure_ascii=False, sort_keys=True)
        )
    root = SGFNode(properties={"GM": 1, "FF": 4, "CA": "UTF-8", "SZ": size, "RU": "Japanese", "C": "\n".join(comment)})

    def coordinate(point):
        return Move((point[0], size - point[1] - 1)).sgf((size, size))

    for color in ("B", "W"):
        root.set_property("A" + color, [coordinate(point) for point in initial.get("stones", {}).get(color, [])])

    def marks(node, value):
        labels = dict(value.get("labels") or {})
        for key, letter in (value.get("letters") or {}).items():
            labels[key] = f"{labels[key]} / {letter}" if key in labels else letter
        node.set_property(
            "LB", [f"{coordinate(tuple(map(int, key.split(','))))}:{label}" for key, label in labels.items()]
        )
        properties = {
            "triangle": "TR",
            "square": "SQ",
            "circle": "CR",
            "cross": "MA",
            "TR": "TR",
            "SQ": "SQ",
            "CR": "CR",
            "MA": "MA",
        }
        for shape, prop in properties.items():
            values = [
                coordinate(tuple(map(int, key.split(","))))
                for key, kind in (value.get("shapes") or {}).items()
                if kind == shape
            ]
            if values:
                node.add_list_property(prop, values)
        node.set_property("SL", [coordinate(point) for point in value.get("highlights") or []])

    marks(root, initial)
    if complete:
        root.set_property("PL", replay["initial"]["to_play"])
        node = root
        for item in replay["moves"]:
            node = node.play(
                Move(None if item["kind"] == "pass" else (item["point"][0], size - item["point"][1] - 1), item["color"])
            )
            if item.get("printed_number") is not None and item["point"] is not None:
                node.set_property("LB", f"{coordinate(item['point'])}:{item['printed_number']}")
        marks(node, payload)
    return root.sgf()
