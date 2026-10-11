"""Offline validate unsigned mixed20 data with each pinned native importer image."""

import gzip
import json
import shlex
import subprocess
from pathlib import Path


D = Path(__file__).parent
IMAGES = {
    "TEST": ("home-ubuntu", "sha256:62283df0e9c81b3367e7865acaa8015a9d4931be9f162b6ec969e80c9073d845"),
    "PROD": ("ucloud-v100", "sha256:ed6112e7006cad941c52ab28f668af0235ddad2d9761128eeee745c63625c67e"),
}
REMOTE = r'''
import gzip,hashlib,json,sys
from pathlib import Path
from katrain.web.kifu.name_candidates import canonical_sha256,validate_bundle
x=json.loads(gzip.decompress(sys.stdin.buffer.read()))
report=validate_bundle(x['bundle'],x['registry'],x['inventory'],x['evidence'],
                       approved_name_snapshot=x['snapshot'])
assert report['ready'] and report['write_ready'] and report['approved']==20,report
files=('identity.py','name_candidates.py','name_evidence.py','name_orthographic.py','name_batch.py','name_inventory.py')
code={name:hashlib.sha256(Path('/app/katrain/web/kifu',name).read_bytes()).hexdigest()for name in files}
assert code==x['expected_code_sha256']
print(json.dumps({'validation':report,'bundle_sha256':canonical_sha256(x['bundle']),
                  'code_sha256':code,'offline_native_validation':True},sort_keys=True))
'''


def read(path):
    with gzip.open(path, "rt") if str(path).endswith(".gz") else open(path) as stream:
        return json.load(stream)


def validate(environment):
    host, image = IMAGES[environment]
    approved = read(D / f"{environment}-mixed20-approved-input.json.gz")
    bundle = read(D / f"{environment}-mixed20-unsigned-bundle.json.gz")
    evidence = read(D / f"{environment}-mixed20-unsigned-evidence.json.gz")
    capture = read(D / f"{environment}-mixed20-fresh-post590-pages.json.gz")
    payload = {"bundle": bundle, "evidence": evidence,
               "registry": approved["registry"], "inventory": approved["inventory"],
               "snapshot": approved["approved_name_snapshot"],
               "expected_code_sha256": capture["code_sha256"]}
    body = gzip.compress(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode(), mtime=0)
    command = (f"docker run --rm --read-only --network none -i --entrypoint python {image} "
               f"-c {shlex.quote(REMOTE)}")
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, command],
                            input=body, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{environment}: {result.stderr.decode(errors='replace')[-1800:]}")
    report = json.loads(result.stdout)
    assert report["bundle_sha256"] == read(D / f"{environment}-mixed20-unsigned-summary.json")["bundle_sha256"]
    path = D / f"{environment}-mixed20-native-validation.json"
    if path.exists():
        raise FileExistsError(path)
    report["image_id"] = image
    path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(environment, "PASS native offline 20/20", report["bundle_sha256"])


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("environment", choices=("TEST", "PROD"))
    args = parser.parse_args()
    validate(args.environment)
