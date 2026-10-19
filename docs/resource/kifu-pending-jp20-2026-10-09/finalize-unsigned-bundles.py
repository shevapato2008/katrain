"""Assemble 20-name bundles after root signs all four finite inner batches; no execution signing."""

import gzip
import json
from pathlib import Path

from katrain.web.kifu.name_candidates import canonical_sha256, validate_bundle
from katrain.web.kifu.name_evidence import validate_transliteration_review
from katrain.web.kifu.name_orthographic import VERSION

DIRECTORY = Path(__file__).parent


def write_json(name, value):
    (DIRECTORY / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def write_gzip(name, value):
    (DIRECTORY / name).write_bytes(gzip.compress(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode(), mtime=0))


def build(environment):
    data = json.load(gzip.open(DIRECTORY / f'{environment}-product-snapshots.json.gz', 'rt'))
    registry = json.loads((DIRECTORY / f'{environment}-source-registry-readonly.json').read_text())['registry']
    anchors = json.loads((DIRECTORY / f'{environment}-anchors.approved.json').read_text())
    bindings = json.loads((DIRECTORY / f'{environment}-preimage-bindings.json').read_text())
    binding_by_key = {(item['owner']['id'], item['lang']): item['binding'] for item in bindings}
    assert len(anchors) == len(binding_by_key) == 20
    rules, batches, candidates, members = [], [], [], []
    for label, language, rule_file in (
        ('jp-to-cn', 'cn', 'jp-rule.approved.json'),
        ('cn-to-tw', 'tw', 'tw-rule.approved.json'),
    ):
        rule = json.loads((DIRECTORY / rule_file).read_text())
        validate_transliteration_review(rule, 'approved_orthographic_rule')
        approved = json.loads((DIRECTORY / f'{environment}-{label}-batch.approved.json').read_text())
        validate_transliteration_review(approved, 'approved_orthographic_batch')
        request = json.loads((DIRECTORY / f'{environment}-{label}-batch-review-request.json').read_text())
        assert approved['content'] == request['content']
        assert all(approved['approval'][field] == request['production'][field]
                   for field in ('content_sha256', 'producer_id', 'producer_model', 'produced_at'))
        rules.append(rule)
        batches.append(approved)
        batch_hash = canonical_sha256(approved)
        for member in approved['content']['members']:
            owner = member['owner']
            assert member['lang'] == language
            members.append({'owner': owner, 'lang': language})
            candidates.append({
                **member, 'decision_kind': 'generated', 'generation_rule_version': VERSION,
                'research_sha256': '', 'orthographic_batch_sha256': batch_hash,
                'review_status': 'approved', 'review_conclusion': 'approved_orthographic_batch',
                'preimage_binding': binding_by_key[(owner['id'], language)],
                **{field: approved['approval'][field] for field in (
                    'producer_id', 'producer_model', 'produced_at', 'reviewer_id', 'reviewer_model', 'reviewed_at')},
            })
    inventory, snapshot = data['inventory'], data['approved_name_snapshot']
    bundle = {'bundle_format': 1, 'inventory_format': inventory['inventory_format'],
              'inventory_sha256': inventory['sha256'], 'registry_version': registry['version'],
              'registry_sha256': canonical_sha256(registry), 'rule_version': 'candidate-v1',
              'catalog_sha256': data['catalog_sha256'], 'members': members,
              'member_set_sha256': canonical_sha256(members), 'candidates': candidates,
              'primary_orthographic': {'version': VERSION, 'rules': rules, 'batches': batches}}
    result = validate_bundle(bundle, registry, inventory, anchors, approved_name_snapshot=snapshot)
    assert len({member['owner']['id'] for member in members}) == len(members) == 20
    assert result['ready'] and result['write_ready'] and result['approved'] == 20, result
    write_gzip(f'{environment}-inventory.json.gz', inventory)
    write_gzip(f'{environment}-approved-name-snapshot.json.gz', snapshot)
    write_json(f'{environment}-source-registry.json', registry)
    write_json(f'{environment}-orthographic-evidence.json', anchors)
    write_gzip(f'{environment}-unsigned-bundle.json.gz', bundle)
    write_json(f'{environment}-unsigned-bundle-summary.json', {
        'status': 'root_dependencies_signed_outer_execution_unsigned', 'environment': environment,
        'bundle_sha256': canonical_sha256(bundle), 'distinct_players': 20, 'name_writes': 20,
        'JP_to_CN_count': 19, 'CN_to_TW_count': 1, 'inner_rules': 2, 'inner_batches': 2,
        'validation': result, 'catalog_sha256': data['catalog_sha256'],
        'inventory_sha256': inventory['sha256'], 'registry_sha256': bundle['registry_sha256'],
        'approved_name_snapshot_sha256': canonical_sha256(snapshot),
        'context_refreshed_at': data['context_refreshed_at'],
    })
    print(environment, '20 names/20 players', canonical_sha256(bundle), 'product validation PASS; outer execution unsigned')


if __name__ == '__main__':
    for environment in ('PROD', 'TEST'):
        build(environment)
