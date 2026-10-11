"""Capture JP-branch qualified product snapshots from TEST and PROD, read only."""

import gzip
import json
import shlex
import subprocess
from pathlib import Path


DIRECTORY = Path(__file__).parent
HOSTS = {
    "PROD": ("ucloud-v100", "katrain-ucloud-katrain-web-1",
             "sha256:16ff2a118049c852d674800d9b0c8e4a676a68e10aca8d8baf67f30f64cd0a0c"),
    "TEST": ("home-ubuntu", "katrain-web",
             "sha256:52907d65efc9e59b8b546d2e335d5d45729aa0eed1c5e1480be7f4cbe0d28259"),
}
REMOTE = """import gzip,json,os,sys
from sqlalchemy import create_engine
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.kifu.name_batch import catalog_snapshot_sha,approved_name_snapshot,orthographic_alias_snapshot
engine=create_engine(os.environ["KATRAIN_DATABASE_URL"],connect_args={"options":"-c default_transaction_read_only=on"})
inventory=build_inventory(engine)
catalog_sha256=catalog_snapshot_sha(engine)
approved=approved_name_snapshot(engine)
with engine.connect() as conn:
    conn.exec_driver_sql("SET TRANSACTION READ ONLY")
    aliases=orthographic_alias_snapshot(conn)
    conn.rollback()
data={"inventory":inventory,"catalog_sha256":catalog_sha256,"approved_name_snapshot":approved,"known_aliases":aliases}
sys.stdout.buffer.write(gzip.compress(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8"),mtime=0))
engine.dispose()
"""


def capture(environment: str):
    host, container, image = HOSTS[environment]
    # Stream the existing DB URL directly into Docker's env-file stdin; no
    # credential is printed, copied to disk, or embedded in process arguments.
    command = (
        f'docker inspect --format "{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}" {container}'
        ' | grep "^KATRAIN_DATABASE_URL="'
        f' | docker run --rm -i --env-file /dev/stdin --network container:{container}'
        f' --entrypoint python {image} -c {shlex.quote(REMOTE)}'
    )
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, command],
        capture_output=True, check=True,
    )
    data = json.loads(gzip.decompress(proc.stdout))
    assert data["inventory"]["counts"]["all"] > 170000
    assert len(data["approved_name_snapshot"]) > 10000
    assert len(data["catalog_sha256"]) == 64
    output = DIRECTORY / f"{environment}-product-snapshots.json.gz"
    output.write_bytes(proc.stdout)
    print(environment, "inventory", data["inventory"]["sha256"],
          "catalog", data["catalog_sha256"],
          "approved names", len(data["approved_name_snapshot"]),
          "aliases", len(data["known_aliases"]),
          "compressed bytes", len(proc.stdout))


if __name__ == "__main__":
    for env in HOSTS:
        capture(env)
