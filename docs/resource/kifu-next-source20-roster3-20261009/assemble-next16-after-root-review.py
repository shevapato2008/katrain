"""Assemble a finite unsigned conventional bundle after root supplies reviewed inputs.

The current draft has 16 native-ready rows. A later four-row replacement must
be added to the source packet and recaptured before it can enter this bundle.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_candidates import canonical_sha256, validate_bundle
from katrain.web.kifu.name_evidence import registry_sha256

D = Path(__file__).resolve().parent


def read(path):
    with gzip.open(path, 'rt') if path.suffix == '.gz' else path.open() as stream:
        return json.load(stream)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def assemble(env, reviewed_path):
    draft_path = D / f'{env}-next16-native-pending-unsigned-draft.json.gz'
    draft = read(draft_path)
    reviewed = read(reviewed_path)
    require(reviewed['environment'] == env and reviewed['status'] == 'root_approved_fresh_context',
            'root reviewed fresh context missing')
    require(reviewed['source_draft_sha256'] == hashlib.sha256(draft_path.read_bytes()).hexdigest(),
            'reviewed source draft differs')
    require(reviewed['registry'] == draft['registry'] and reviewed['owners'] == draft['owners'],
            'reviewed registry or owner preimages changed')
    require(reviewed['catalog_sha256'] == draft['catalog_sha256'], 'catalog changed')
    require(reviewed['latest_batch']['id'] == draft['latest_batch']['id'], 'preceding batch changed')
    approved = reviewed['candidates']
    pending = draft['candidates']
    require(len(approved) == len(pending) == 16, 'exact 16 reviewed candidates required')
    by_key = {(x['owner']['id'], x['lang']): x for x in approved}
    require(len(by_key) == 16, 'duplicate or missing candidate')
    review_keys = {'review_status', 'reviewer_id', 'reviewer_model', 'reviewed_at',
                   'review_conclusion', 'excluded_candidates', 'conflict_adjudication'}
    for old in pending:
        key = (old['owner']['id'], old['lang'])
        new = by_key[key]
        require(new['review_status'] == 'approved', f'{key}: review absent')
        for field in old:
            if field not in review_keys:
                require(old[field] == new.get(field), f'{key}: source/CAS field changed: {field}')
    inventory = reviewed['inventory']
    registry = draft['registry']
    members = [{'owner': x['owner'], 'lang': x['lang']} for x in approved]
    bundle = {
        'bundle_format': 2, 'inventory_format': inventory['inventory_format'],
        'inventory_sha256': inventory['sha256'],
        'registry_version': registry['version'], 'registry_sha256': registry_sha256(registry),
        'rule_version': 'candidate-v1', 'catalog_sha256': reviewed['catalog_sha256'],
        'members': members, 'member_set_sha256': canonical_sha256(members),
        'candidates': approved,
        'owners': draft['owners'], 'owner_set_sha256': canonical_sha256(draft['owners']),
        'album_links': [], 'link_set_sha256': canonical_sha256([]),
    }
    require(bundle.get('transliteration') is None and bundle.get('primary_orthographic') is None,
            'this conventional bundle must not require global approved-name snapshot')
    report = validate_bundle(bundle, registry, inventory, draft['research'])
    require(report['ready'] and report['write_ready'] and report['approved'] == 16,
            f'native bundle validation failed: {report}')
    for kind, value in [('bundle', bundle), ('evidence', draft['research']), ('validation-report', report)]:
        path = D / f'{env}-next16-unsigned-{kind}.json.gz'
        require(not path.exists(), f'refusing to overwrite {path}')
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        path.write_bytes(gzip.compress(raw, mtime=0))
        print(env, kind, path.name, hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--env', choices=['PROD', 'TEST'], required=True)
    parser.add_argument('--root-reviewed-fresh', type=Path, required=True)
    args = parser.parse_args()
    assemble(args.env, args.root_reviewed_fresh)
