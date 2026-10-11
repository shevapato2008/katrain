"""Freeze 19 exact JP-to-CN names and one CN-to-TW name without approvals."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_orthographic import VERSION

DIRECTORY = Path(__file__).parent
PRODUCER = '/root/next_batch_source_recovery'
MODEL = 'GPT-6 (exact runtime variant unavailable)'


def write(name, value):
    (DIRECTORY / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def production(content):
    return {'producer_id': PRODUCER, 'producer_model': MODEL,
            'produced_at': datetime.now(timezone.utc).isoformat(),
            'content_sha256': registry_sha256(content)}


def build():
    requests, manifest, anchors = [], [], []
    source_files = {}
    pairs = {}
    for environment in ('PROD', 'TEST'):
        path = DIRECTORY / f'{environment}-jp-source-readonly.json'
        captured = json.loads(path.read_text())
        assert len(captured['rows']) == 20
        source_files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        members = []
        for row in captured['rows']:
            assert row['current_target'] is None
            assert row['source_qualified_product_gate'] and row['verified_source_live_new_JP_branch']
            content = row['unsigned_anchor_content']
            original = content['original_name']
            target = row['target_display']
            name, evidence = row['source_name'], row['source_evidence']
            if row['target_language'] == 'cn':
                assert original == target and name['lang'] == 'jp'
            else:
                assert (row['id'], original, target) == ((4340 if environment == 'PROD' else 10134), '安东阳向', '安東陽向')
            assert name['display_name'] == evidence['candidate_name'] == original
            changes = [{'position': index, 'input': f'U+{ord(a):04X}', 'output': f'U+{ord(b):04X}'}
                       for index, (a, b) in enumerate(zip(original, target))]
            request = {'environment': environment, 'evidence_kind': 'primary_orthographic',
                       'version': 1, 'content': content, 'production': production(content)}
            requests.append(request)
            anchors.append({'environment': environment, 'content': content,
                            'candidate_display': target, 'target_language': row['target_language']})
            member = {'owner': content['owner'], 'original_name': original,
                      'lang': row['target_language'], 'display_name': target,
                      'reference_kind': content['reference_kind'],
                      'codepoint_changes': changes, 'name_preimage_sha256': None,
                      'source_anchor_content_sha256': registry_sha256(content),
                      'source_name_sha256': registry_sha256(name),
                      'source_evidence_sha256': registry_sha256(evidence),
                      'source_batch_id': row['source_batch']['id'],
                      'source_qualified_product_gate': True,
                      'verified_source_live_new_JP_branch': True}
            members.append(member)
            item = {'environment': environment, 'player_id': row['id'],
                    'canonical_name': row['canonical_name'], 'source_display': original,
                    'target_language': row['target_language'], 'candidate_display': target,
                    'source_evidence_id': evidence['id'], 'source_batch_id': row['source_batch']['id'],
                    'source_name_sha256': registry_sha256(name),
                    'source_evidence_sha256': registry_sha256(evidence),
                    'unsigned_anchor_content_sha256': registry_sha256(content),
                    'linked_games': row['games'], 'target_preimage': None}
            if row['target_language'] == 'tw':
                item.update(cn_display=original, candidate_tw_display=target)
            manifest.append(item)
            pairs.setdefault(original, {})[environment] = {'id': row['id'], 'members': row['linked_album_members']}
        write(f'{environment}-unsigned-member-packet.json', {
            'status': 'pending_root_anchor_rule_batch_signatures', 'environment': environment,
            'source_capture_file': path.name, 'source_capture_file_sha256': source_files[path.name],
            'source_captured_at': captured['captured_at'], 'members': members,
            'members_sha256': registry_sha256(members),
            'count': 20, 'JP_to_CN_count': 19, 'CN_to_TW_count': 1,
            'target_null_preimages': 20, 'linked_games_sum': sum(r['games'] for r in captured['rows']),
            'approval_dependencies_missing': ['signed_original_anchors', 'signed_two_rules',
                                              'signed_inner_batches', 'outer_execution_approval'],
        })
    assert len(pairs) == 20
    for original, pair in pairs.items():
        assert set(pair) == {'PROD', 'TEST'}
        prod, test = pair['PROD'], pair['TEST']
        # Identity IDs differ; linked game IDs and original SGF name/date scope agree.
        columns = ('id', 'date_played', 'player_black', 'player_white', 'black_rank', 'white_rank', 'result', 'sgf_utf8_sha256', 'side')
        assert [{k: r[k] for k in columns} for r in prod['members']] == [{k: r[k] for k in columns} for r in test['members']], original
    rule = {'version': VERSION, 'reference_kind': 'verified_japanese_display',
            'lang': 'cn', 'source_lang': 'ja', 'source_script': 'Kanji',
            'target_script': 'Kanji', 'target_region': 'CN', 'preservation': 'exact_codepoints'}
    write('unsigned-jp-rule-request.json', {'status': 'pending_root_independent_rule_approval',
                                         'content': rule, 'production': production(rule)})
    write('unsigned-anchor-review-requests.json', {'status': 'pending_root_independent_original_approval', 'rows': requests})
    write('unsigned-anchor-content.json', anchors)
    write('unsigned-manifest.json', {'status': 'unsigned_pending_root_review', 'rows': manifest})
    write('cross-environment-source-pairs.json', {
        'pairs': [{'original_name': name, 'prod_id': pair['PROD']['id'], 'test_id': pair['TEST']['id'],
                   'linked_games': len(pair['PROD']['members']), 'equal_original_game_scope': True}
                  for name, pair in pairs.items()],
        'source_capture_files': source_files,
    })
    print('prepared', len(requests), 'unsigned anchors; each environment 19 exact CN + 1 finite TW; no approvals')


if __name__ == '__main__':
    build()
