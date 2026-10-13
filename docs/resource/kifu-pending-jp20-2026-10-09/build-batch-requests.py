"""Build two unsigned finite inner batches per environment after root signs sources/rules."""

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_evidence import (
    registry_sha256, validate_primary_orthographic_anchor, validate_transliteration_review,
)
from katrain.web.kifu.name_orthographic import VERSION

DIRECTORY = Path(__file__).parent
PRODUCER = '/root/next_batch_source_recovery'
MODEL = 'GPT-6 (exact runtime variant unavailable)'


def now():
    return datetime.now(timezone.utc).isoformat()


def write(name, value):
    (DIRECTORY / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def build(environment):
    captured = json.load(gzip.open(DIRECTORY / f'{environment}-product-snapshots.json.gz', 'rt'))
    assert captured.get('context_refreshed_at'), 'global context must be refreshed after preceding batch 588'
    rows = json.loads((DIRECTORY / f'{environment}-unsigned-member-packet.json').read_text())['members']
    anchors = json.loads((DIRECTORY / f'{environment}-anchors.approved.json').read_text())
    assert len(rows) == len(anchors) == 20
    for anchor in anchors:
        validate_primary_orthographic_anchor(anchor)
    anchors_by_id = {anchor['content']['owner']['id']: anchor for anchor in anchors}
    snapshot = captured['approved_name_snapshot']
    aliases = captured['known_aliases']
    scope = []
    for row in rows:
        owner = row['owner']
        anchor = anchors_by_id[owner['id']]
        source_language = 'jp' if row['lang'] == 'cn' else 'cn'
        source = [item for item in snapshot if item['owner'] == owner and item['lang'] == source_language]
        assert len(source) == 1 and source[0]['decision_kind'] == 'conventional'
        assert source[0]['display_name'] == row['original_name'] == anchor['content']['original_name']
        assert source[0]['name_sha256'] == row['source_name_sha256']
        assert source[0]['evidence_sha256'] == row['source_evidence_sha256']
        assert not any(item['owner'] == owner and item['lang'] == row['lang'] for item in snapshot)
        key = normalize_alias(row['display_name'])
        assert not any(item['owner'] != owner and item['lang'] == row['lang']
                       and normalize_alias(item['display_name']) == key for item in snapshot)
        assert not any(item['owner'] != owner and normalize_alias(item['name']) == key for item in aliases)
        scope.append({'owner': owner, 'lang': row['lang'], 'name_preimage_sha256': None,
                      'source_anchor_sha256': registry_sha256(anchor),
                      'source_name_sha256': row['source_name_sha256'],
                      'source_evidence_sha256': row['source_evidence_sha256']})
    assert len(scope) == 20
    capture_time = captured['context_refreshed_at']
    raw_sources = json.loads((DIRECTORY / f'{environment}-jp-source-readonly.json').read_text())
    capture = {'environment': environment, 'captured_at': capture_time,
               'context_refreshed_at': captured['context_refreshed_at'],
               'literal_target_NULL_captured_at': raw_sources['captured_at'],
               'inventory_sha256': captured['inventory']['sha256'],
               'catalog_sha256': captured['catalog_sha256'],
               'approved_name_snapshot_sha256': registry_sha256(snapshot),
               'known_aliases_sha256': registry_sha256(aliases), 'scope': scope}
    capture_hash = registry_sha256(capture)
    write(f'{environment}-preimage-binding-capture.json', capture)
    all_bindings = []
    for label, language, rule_file, expected_count in (
        ('jp-to-cn', 'cn', 'jp-rule.approved.json', 19),
        ('cn-to-tw', 'tw', 'tw-rule.approved.json', 1),
    ):
        rule = json.loads((DIRECTORY / rule_file).read_text())
        validate_transliteration_review(rule, 'approved_orthographic_rule')
        rule_hash = registry_sha256(rule)
        subset = [row for row in rows if row['lang'] == language]
        assert len(subset) == expected_count
        produced_at = now()
        assert datetime.fromisoformat(produced_at) > datetime.fromisoformat(rule['approval']['reviewed_at'])
        assert all(datetime.fromisoformat(produced_at) > datetime.fromisoformat(anchors_by_id[row['owner']['id']]['approval']['reviewed_at']) for row in subset)
        members = []
        for row in subset:
            owner = row['owner']
            anchor_hash = registry_sha256(anchors_by_id[owner['id']])
            candidate_source = {'owner': owner, 'lang': language, 'display_name': row['display_name'],
                                'decision_kind': 'generated', 'generation_rule_version': VERSION,
                                'name_preimage_sha256': None, 'source_anchor_sha256': anchor_hash,
                                'rule_sha256': rule_hash}
            binding = {'actor_id': PRODUCER, 'actor_model': MODEL,
                       'captured_at': capture_time, 'bound_at': now(),
                       'name_preimage_sha256': None,
                       'source_candidate_sha256': registry_sha256(candidate_source),
                       'capture_sha256': capture_hash}
            all_bindings.append({'owner': owner, 'lang': language, 'binding': binding})
            members.append({'owner': owner, 'original_name': row['original_name'], 'lang': language,
                            'display_name': row['display_name'], 'source_anchor_sha256': anchor_hash,
                            'rule_sha256': rule_hash, 'codepoint_changes': row['codepoint_changes'],
                            'name_preimage_sha256': None, 'preimage_binding_sha256': registry_sha256(binding),
                            'reference_kind': row['reference_kind']})
        frozen_at = now()
        content = {'version': VERSION, 'rule_sha256': rule_hash, 'members': members,
                   'members_sha256': registry_sha256(members), 'catalog_sha256': captured['catalog_sha256'],
                   'approved_name_snapshot_sha256': registry_sha256(snapshot), 'known_aliases': aliases,
                   'unresolved_conflicts': [], 'complete_name_review': members,
                   'sampled_members': [registry_sha256(member) for member in members], 'frozen_at': frozen_at}
        request = {'status': 'pending_root_independent_batch_approval', 'content': content,
                   'production': {'producer_id': PRODUCER, 'producer_model': MODEL,
                                  'produced_at': produced_at, 'content_sha256': registry_sha256(content)},
                   'dependencies': {'rule_sha256': rule_hash,
                                    'anchor_sha256': sorted(member['source_anchor_sha256'] for member in members),
                                    'preimage_capture_sha256': capture_hash}}
        write(f'{environment}-{label}-batch-review-request.json', request)
        print(environment, label, 'members', len(members), 'request', registry_sha256(content))
    write(f'{environment}-preimage-bindings.json', all_bindings)
    assert len(all_bindings) == 20


if __name__ == '__main__':
    for environment in ('PROD', 'TEST'):
        build(environment)
