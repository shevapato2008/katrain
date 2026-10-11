"""Capture the exact CN source rows for the pending 20-player TW display packet."""

import json
import subprocess
from datetime import datetime
from pathlib import Path


PAIRS = [
    (6752, 12521), (6765, 12534), (6768, 12537), (5365, 11141),
    (5211, 10991), (3993, 9789), (6713, 12482), (6447, 12211),
    (5581, 11354), (6376, 12142), (5893, 11662), (4552, 10342),
    (3906, 9703), (5933, 11702), (4023, 9819), (4572, 10362),
    (5040, 10822), (4801, 10588), (6215, 11981), (6458, 12222),
]
HOSTS = {
    "PROD": ("ucloud-v100", "katrain-ucloud-postgres-1"),
    "TEST": ("home-ubuntu", "katrain-postgres"),
}


def capture(environment: str, ids: list[int]) -> dict:
    host, container = HOSTS[environment]
    values = ",".join(f"({number})" for number in ids)
    sql = f"""
BEGIN READ ONLY;
SET LOCAL statement_timeout = '30s';
WITH target(id) AS (VALUES {values}), rows AS (
 SELECT p.id, p.canonical_name,
        row_to_json(n) AS source_name,
        row_to_json(e) AS source_evidence,
        row_to_json(b) AS source_batch,
        row_to_json(tw) AS current_tw,
        (SELECT count(*) FROM kifu_albums a WHERE a.black_player_id=p.id OR a.white_player_id=p.id) AS games
 FROM target x JOIN kifu_players p ON p.id=x.id
 LEFT JOIN kifu_player_names n ON n.player_id=p.id AND n.lang='cn'
 LEFT JOIN kifu_name_research_evidence e ON e.id=n.evidence_id
 LEFT JOIN LATERAL (
   SELECT batches.id,batches.bundle_sha256,batches.status
   FROM kifu_name_changes changes
   JOIN kifu_name_batches batches ON batches.id=changes.batch_id
   WHERE changes.target_table='kifu_name_research_evidence'
     AND changes.target_row_id=e.id
   ORDER BY batches.id DESC LIMIT 1
 ) b ON true
 LEFT JOIN kifu_player_names tw ON tw.player_id=p.id AND tw.lang='tw'
)
SELECT json_build_object('environment','{environment}','rows',
  (SELECT json_agg(row_to_json(rows) ORDER BY id) FROM rows));
ROLLBACK;
"""
    remote_command = (
        f"docker exec -i {container} sh -c "
        "'psql -X -qAt -v ON_ERROR_STOP=1 -U \"$POSTGRES_USER\" "
        "-d \"$POSTGRES_DB\"'"
    )
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, remote_command],
        input=sql, text=True, capture_output=True, check=True,
    )
    lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    if len(lines) != 1:
        raise RuntimeError(f"{environment}: unexpected query output, {len(lines)} JSON rows")
    data = json.loads(lines[0])
    if sorted(row["id"] for row in data["rows"]) != sorted(ids):
        raise RuntimeError(f"{environment}: owner IDs missing from live DB")
    # PostgreSQL JSON trims trailing fractional zeros; product _image uses
    # datetime.isoformat(), which retains six digits for nonzero microseconds.
    for row in data["rows"]:
        for key in ("source_name", "source_evidence", "current_tw"):
            image = row[key]
            if image is not None:
                for field, value in image.items():
                    if field.endswith("_at") and value is not None:
                        image[field] = datetime.fromisoformat(value).isoformat()
    return data


if __name__ == "__main__":
    directory = Path(__file__).parent
    for env, position in (("PROD", 0), ("TEST", 1)):
        result = capture(env, [pair[position] for pair in PAIRS])
        (directory / f"{env}-cn-source-readonly.json").write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        )
        rows = result["rows"]
        print(env, len(rows), "CN", sum(row["source_name"] is not None for row in rows),
              "TW NULL", sum(row["current_tw"] is None for row in rows),
              "source batches", sum(row["source_batch"] is not None for row in rows))
