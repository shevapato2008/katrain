"""Package reviewed unsigned 16-name bundle; root alone signs and invokes it."""
import argparse
import gzip
import hashlib
import json
import tarfile
from pathlib import Path

from katrain.web.kifu.name_candidates import validate_bundle
from katrain.web.kifu.name_evidence import registry_sha256

D = Path(__file__).resolve().parent


def read(path):
    with gzip.open(path, 'rt') if path.suffix == '.gz' else path.open() as stream:
        return json.load(stream)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value, *, gz=False, jsonl=False):
    if jsonl:
        raw = ('\n'.join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
                         for row in value) + '\n').encode()
    else:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        if gz:
            raw = gzip.compress(raw, mtime=0)
    if path.exists():
        raise FileExistsError(path)
    path.write_bytes(raw)
    return sha(path)


def prepare(images):
    files = []
    manifest = {'required_image_ids': images, 'expected_candidate_count': 16,
                'expected_decisions': {'conventional': 16, 'generated': 0},
                'expected_languages': {'ko': 13, 'jp': 1, 'tw': 1, 'en': 1}}
    for env in ('PROD', 'TEST'):
        bundle_src = D / f'{env}-next16-unsigned-bundle.json.gz'
        evidence_src = D / f'{env}-next16-unsigned-evidence.json.gz'
        reviewed_path = D / f'{env}-root-reviewed-fresh.json.gz'
        scoped_path = D / f'{env}-next16-current-scoped-readonly.json.gz'
        bundle, evidence, reviewed, scoped = (read(path) for path in
                                              (bundle_src, evidence_src, reviewed_path, scoped_path))
        registry = reviewed['registry']
        inventory = reviewed['inventory']
        assert reviewed['status'] == 'root_approved_fresh_context'
        assert len(bundle['candidates']) == len(evidence) == 16
        assert all(row['decision_kind'] == 'conventional' for row in bundle['candidates'])
        assert {lang: sum(row['lang'] == lang for row in bundle['candidates'])
                for lang in ('ko', 'jp', 'tw', 'en')} == manifest['expected_languages']
        assert bundle['registry_sha256'] == registry_sha256(registry)
        assert bundle['inventory_sha256'] == inventory['sha256']
        assert scoped['catalog_sha256'] == bundle['catalog_sha256']
        report = validate_bundle(bundle, registry, inventory, evidence)
        assert report['ready'] and report['write_ready'] and report['approved'] == 16
        bundle_dst = D / f'{env}-next16-bundle.json.gz'
        if bundle_dst.exists():
            raise FileExistsError(bundle_dst)
        bundle_dst.write_bytes(bundle_src.read_bytes())
        inventory_dst = D / f'{env}-next16-inventory.json.gz'
        evidence_dst = D / f'{env}-next16-evidence.jsonl'
        registry_dst = D / f'{env}-next16-registry.json'
        entry = {'bundle_sha256': registry_sha256(bundle), 'bundle_file_sha256': sha(bundle_dst),
                 'inventory_file_sha256': save(inventory_dst, inventory, gz=True),
                 'evidence_file_sha256': save(evidence_dst, evidence, jsonl=True),
                 'registry_file_sha256': save(registry_dst, registry),
                 'scoped_capture_file_sha256': sha(scoped_path),
                 'reviewed_fresh_file_sha256': sha(reviewed_path),
                 'scope_album_count': scoped['unique_albums'], 'scope_game_slots': scoped['game_slots']}
        manifest[env] = entry
        files += [bundle_dst, inventory_dst, evidence_dst, registry_dst, scoped_path]
    manifest['helper_sha256'] = {name: sha(D / name) for name in ('next16-inner.py', 'next16-run.py')}
    manifest_path = D / 'next16-execution-proposed-manifest.json'
    save(manifest_path, manifest)
    files += [manifest_path, D / 'next16-inner.py', D / 'next16-run.py']
    transport = D / 'next16-execution-transport.tar.gz'
    if transport.exists():
        raise FileExistsError(transport)
    with tarfile.open(transport, 'w:gz') as tar:
        for path in files:
            tar.add(path, arcname=path.name)
    print(json.dumps({'manifest_sha256': sha(manifest_path), 'transport_sha256': sha(transport),
                      'bundle_sha256': {env: manifest[env]['bundle_sha256'] for env in ('PROD', 'TEST')}},
                     ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prod-image', required=True)
    parser.add_argument('--test-image', required=True)
    args = parser.parse_args()
    images = {'PROD': args.prod_image, 'TEST': args.test_image}
    assert all(value.startswith('sha256:') and len(value) == 71 for value in images.values())
    prepare(images)
