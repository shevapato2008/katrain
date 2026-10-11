"""Pure check that stale or altered source proposals cannot enter unsigned binding."""

from copy import deepcopy
import json
from pathlib import Path

from bind_unsigned import verify_source_binding
from katrain.web.kifu.name_candidates import canonical_sha256


D = Path(__file__).resolve().parent


def main():
    selection = json.loads((D / "selection.json").read_text())
    packet = json.loads((D / "source-packet.json").read_text())
    records = []
    for source in selection["sources"]:
        by_raw = {row["raw_value"]: row for row in packet["sources"][source["file"]]["records"]}
        for raw in source["raw_values"]:
            row = by_raw[raw]
            records.append({"raw_value": raw, "profile": source["profile"], "source_file": source["file"],
                            "owner_id_hint": row.get("owner_id_from_2026_10_04_snapshot",
                                                     row.get("raw_owner_id_hint_2026_10_04")),
                            "old_parts": row.get("parts", row.get("old_parser_parts")),
                            "core": row["core"], "names": row["names"]})
    capture = {"raw_count_requested": 150, "records": records,
               "selection_sha256": canonical_sha256(selection),
               "source_packet_sha256": canonical_sha256(packet)}
    verify_source_binding(capture, selection, packet)

    stale_packet = deepcopy(packet)
    first = selection["sources"][0]["file"]
    stale_packet["sources"][first]["records"][0]["names"]["en"] += " changed"
    for altered_capture, altered_packet in ((capture, stale_packet),
                                            (deepcopy(capture), packet)):
        if altered_packet is packet:
            altered_capture["records"][0]["names"]["en"] += " changed"
        try:
            verify_source_binding(altered_capture, selection, altered_packet)
        except AssertionError:
            pass
        else:
            raise AssertionError("stale packet or captured proposal was accepted")
    print("matching source accepted; stale packet and altered captured proposal rejected")


if __name__ == "__main__":
    main()
