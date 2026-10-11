"""Offline format-2 unsigned assembly after root supplies fresh approved input.

This script does not approve, sign, connect to a DB, or write outside this
research directory. It rejects changes to the pending source research or CAS.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_candidates import canonical_sha256, validate_bundle
from katrain.web.kifu.name_evidence import registry_sha256

D = Path(__file__).parent
REGISTRY = json.loads((D / 'source-registry-proposed-pending.json').read_text())
SOURCE = json.loads((D / 'source20-post591-final-pending.json').read_text())


def read(path):
    with gzip.open(path, 'rt') if path.suffix == '.gz' else path.open() as stream:
        return json.load(stream)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def assemble(env, approved_path):
    fresh = read(approved_path)
    draft = read(D / f'{env}-post591-final20-native-pending-unsigned-draft.json.gz')
    require(fresh['environment'] == env and
            fresh['status'] == 'root_approved_fresh_current591_global_context',
            'root reviewed fresh context missing')
    require(fresh['preceding_batch_applied'] == 591 and fresh['pages_synchronized'] is True,
            'preceding batch/page context incomplete')
    require(fresh['registry'] == REGISTRY,
            'reviewed registry differs from proposed exact registry; regenerate research if registry changes')
    approved = fresh['candidates']
    pending = draft['candidates']
    require(len(approved) == len(pending) == 20, 'exact 20 approved candidates required')
    by_key = {(x['owner']['id'], x['lang']): x for x in approved}
    require(len(by_key) == 20, 'duplicate or missing candidate')
    allowed_review_keys = {'review_status', 'reviewer_id', 'reviewer_model', 'reviewed_at',
                           'review_conclusion', 'generated_review', 'excluded_candidates',
                           'conflict_adjudication'}
    for original in pending:
        key = (original['owner']['id'], original['lang'])
        candidate = by_key[key]
        require(candidate['review_status'] == 'approved', f'{key}: review not approved')
        for field in original:
            if field not in allowed_review_keys:
                require(candidate.get(field) == original[field], f'{key}: pending source/CAS field changed: {field}')
        require(candidate['name_preimage_sha256'] == original['name_preimage_sha256'] and
                candidate['preimage_binding'] == original['preimage_binding'],
                f'{key}: target 13-field preimage binding changed')
        if candidate['decision_kind'] == 'generated':
            require(candidate['generated_review']['decision'] == 'approve_generated',
                    f'{key}: affirmative generated review missing')
    require({(x['prod_player_id'], x['proposed_name']) for x in SOURCE['players']} ==
            {(x['prod_player_id'], x['proposed_display_name']) for x in
             read(D / f'{env}-post591-final20-unsigned-pending-input.json.gz')['pending']},
            'source packet membership changed')
    owners = draft['owners']
    require(fresh['owners'] == owners, 'fresh owner preimages differ from bounded current-591 capture')
    inventory = fresh['inventory']
    snapshot = fresh['approved_name_snapshot']
    research = draft['research']
    members = [{'owner': x['owner'], 'lang': x['lang']} for x in approved]
    bundle = {
        'bundle_format': 2, 'inventory_format': inventory['inventory_format'],
        'inventory_sha256': inventory['sha256'],
        'registry_version': REGISTRY['version'], 'registry_sha256': registry_sha256(REGISTRY),
        'rule_version': 'candidate-v1', 'catalog_sha256': fresh['catalog_sha256'],
        'members': members, 'member_set_sha256': canonical_sha256(members),
        'candidates': approved,
        'owners': owners, 'owner_set_sha256': canonical_sha256(owners),
        'album_links': [], 'link_set_sha256': canonical_sha256([]),
    }
    report = validate_bundle(bundle, REGISTRY, inventory, research,
                             approved_name_snapshot=snapshot)
    require(report['ready'] and report['write_ready'] and report['approved'] == 20,
            f'native format-2 bundle validation failed: {report}')
    for kind, value in [('bundle', bundle), ('evidence', research), ('validation-report', report)]:
        path = D / f'{env}-post591-final20-unsigned-{kind}.json.gz'
        require(not path.exists(), f'refusing to overwrite {path}')
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        path.write_bytes(gzip.compress(raw, mtime=0))
        print(env, kind, path.name, hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--env', choices=['PROD', 'TEST'], required=True)
    parser.add_argument('--root-approved-fresh-input', type=Path, required=True)
    args = parser.parse_args()
    assemble(args.env, args.root_approved_fresh_input)
