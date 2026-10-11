"""Offline unsigned binding of 610 literal name cells after owner approval.

Requires fresh TEST/PROD post-owner capture JSON.gz files with the same record
shape as the earlier exact-scope captures. Does no database access or signing.
"""

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.raw_event_translation import eligible_raw_title_owner, validate_english_literal_parts


D = Path(__file__).resolve().parent
MATRIX = json.loads((D / 'sgf_english-name-matrix-unsigned.json').read_text())
MANIFEST = json.loads((D / 'sgf_english-owner-research-unsigned.json').read_text())
LANGS = ('cn', 'tw', 'jp', 'ko', 'en')
PRODUCER_ID = '/root/event_literal_fresh_binding'
PRODUCER_MODEL = 'gpt-6-sol'
if not __debug__:
    raise RuntimeError('name binding assertions must be enabled')


def read(environment):
    path = D / f'{environment}-postowner-capture.json.gz'
    return json.loads(gzip.decompress(path.read_bytes())), hashlib.sha256(path.read_bytes()).hexdigest()


def bind(test, prod, hashes):
    captures = {'TEST': test, 'PROD': prod}
    rows_by_env = {}
    matrix = {row['raw_value']: row for row in MATRIX['records']}
    assert len(matrix) == 122 and MATRIX['proposed_name_cells'] == 610
    for env, cap in captures.items():
        assert cap['environment'] == env and cap['status'] == 'post_owner_read_only'
        assert cap['ready_for_unsigned_name_review'] and cap['raw_count_requested'] == 122
        assert cap['inventory_sha256'] == MANIFEST['member_manifest'][env]['inventory_sha256']
        assert cap['catalog_sha256'] and cap['captured_at']
        assert cap['physical_optional_album_columns'] == ['event_edition_id', 'list_hidden_reason']
        assert not any(collision['raw_value'] in matrix for collision in cap['external_collisions'])
        rows = {row['raw_value']: row for row in cap['records'] if row['raw_value'] in matrix}
        assert len(rows) == 122 and set(rows) == set(matrix)
        assert sum(len(row['album_ids']) for row in rows.values()) == 938
        for raw, row in rows.items():
            source = matrix[raw]
            owner = row['owner']
            assert owner['id'] == source['owner_id'][env] and owner['raw_value'] == raw
            assert eligible_raw_title_owner(owner)
            assert owner['review_metadata']['sgf_literal']['profile'] == 'sgf_english'
            assert owner['review_metadata']['scope_sha256'] == source['scope_sha256'][env]
            assert validate_english_literal_parts(raw, row['current_parts'])
            assert row['current_parts'] == source['raw_parts']
            assert row['scope_sha256'] == source['scope_sha256'][env]
            assert len(row['scope_rows']) == len(row['original_sgf_refs']) == len(row['album_ids'])
            assert all(ref['gn_values'][0] == raw and ref['ev_values'] == [] for ref in row['original_sgf_refs'])
            assert all(value['event_edition_id'] is None and value['list_hidden_reason'] is None
                       for value in row['optional_album_preimages'].values())
            assert len(row['full_physical_album_sha256']) == 64
            assert not row['name_preimages'] and not row['evidence_preimages']
            assert set(source['names']) == set(LANGS)
        rows_by_env[env] = rows
    return {'status': 'unsigned_postowner_name_binding', 'raw_owners': 122,
            'proposed_name_cells': 610, 'current_games': 938,
            'source_matrix_canonical_sha256': canonical_sha256(MATRIX),
            'owner_manifest_canonical_sha256': canonical_sha256(MANIFEST),
            'postowner_capture_file_sha256': hashes,
            'catalog_sha256': {env: cap['catalog_sha256'] for env, cap in captures.items()},
            'inventory_sha256': {env: cap['inventory_sha256'] for env, cap in captures.items()},
            'owner_afterimage_sha256': {env: {raw: canonical_sha256(row['owner']) for raw, row in rows.items()}
                                       for env, rows in rows_by_env.items()},
            'full_physical_album_sha256': {env: {raw: row['full_physical_album_sha256']
                                                for raw, row in rows.items()} for env, rows in rows_by_env.items()},
            'name_preimage_sha256': {env: {raw: {lang: None for lang in LANGS} for raw in matrix}
                                     for env in captures},
            'records': MATRIX['records'], 'approval': None}


def build_name_artifacts(environment, capture, capture_sha, binding, bound_at):
    registry_row = capture['latest_registry']
    registry = registry_row['registry']
    assert registry_row['version'] == registry['version']
    assert registry_row['sha256'] == registry_sha256(registry)
    rows = {row['raw_value']: row for row in capture['records']}
    owners, members, candidates, research = [], [], [], []
    produced_at = MATRIX.get('produced_at') or MANIFEST['assembled_at']
    assert produced_at <= bound_at and capture['captured_at'] <= bound_at
    for source in MATRIX['records']:
        raw = source['raw_value']
        row = rows[raw]
        owner = {'kind': 'raw_event', 'id': row['owner']['id']}
        ids = row['album_ids']
        owners.append({'owner': owner, 'preimage': row['owner'],
                       'occurrence_album_ids': ids, 'occurrence_sha256': canonical_sha256(ids)})
        for lang in LANGS:
            name = source['names'][lang]
            research_row = {
                'candidate_name': name, 'lang': lang, 'original_language': 'en',
                'original_language_basis': 'reviewed_sgf_gn', 'original_name': source['core_key'],
                'original_sgf_refs': row['original_sgf_refs'], 'owner': owner,
                'produced_at': produced_at, 'producer_id': PRODUCER_ID, 'producer_model': PRODUCER_MODEL,
                'raw_parts': source['raw_parts'], 'raw_value': raw,
                'registry_sha256': registry_row['sha256'], 'registry_version': registry['version'],
                'reuse_note': 'Shared core lexicon reused only for literal title composition; no event identity claim.',
                'review_status': 'pending', 'scope_status': 'translated_from_original',
                'sgf_literal_evidence': {'captured_at': capture['captured_at'],
                    'scope_file': f'{environment}-postowner-capture.json.gz',
                    'owner_profile': 'sgf_english', 'raw_parts_sha256': canonical_sha256(source['raw_parts']),
                    'scope_rows': row['scope_rows'], 'scope_sha256': row['scope_sha256']},
                'source_basis': 'sgf_literal_v1', 'source_checks': [],
                'translation_method': 'literal_event_title',
                'translation_note': 'Literal first-GN SGF title and reviewed shared English core lexicon; no official multilingual identity claim.',
                'translation_support': []}
            research.append(research_row)
            members.append({'lang': lang, 'owner': owner, 'raw_value': raw})
            candidates.append({
                'decision_kind': 'translated', 'display_name': name,
                'generation_rule_version': 'raw-event-title-translation-v1',
                'lang': lang, 'name_preimage_sha256': None, 'owner': owner,
                'preimage_binding': {'actor_id': PRODUCER_ID, 'actor_model': PRODUCER_MODEL,
                    'bound_at': bound_at, 'captured_at': capture['captured_at'],
                    'capture_sha256': capture_sha, 'name_preimage_sha256': None},
                'produced_at': produced_at, 'producer_id': PRODUCER_ID,
                'producer_model': PRODUCER_MODEL, 'raw_value': raw,
                'research_sha256': canonical_sha256(research_row), 'review_status': 'pending',
                'translation_method': 'literal_event_title'})
    assert len(owners) == 122 and len(members) == len(candidates) == len(research) == 610
    bundle = {'album_links': [], 'bundle_format': 2, 'candidates': candidates,
              'catalog_sha256': capture['catalog_sha256'], 'inventory_format': 4,
              'inventory_sha256': capture['inventory_sha256'],
              'link_set_sha256': canonical_sha256([]), 'member_set_sha256': canonical_sha256(members),
              'members': members, 'owner_set_sha256': canonical_sha256(owners), 'owners': owners,
              'registry_sha256': registry_row['sha256'], 'registry_version': registry['version'],
              'rule_version': 'candidate-v1'}
    return {'environment': environment, 'status': 'pending_independent_name_review',
            'postowner_capture_file_sha256': capture_sha,
            'source_matrix_canonical_sha256': binding['source_matrix_canonical_sha256'],
            'produced_at': produced_at, 'bound_at': bound_at,
            'producer_id': PRODUCER_ID, 'producer_model': PRODUCER_MODEL,
            'registry': registry, 'research_records': research, 'name_bundle': bundle,
            'approval': None}


def main():
    outputs = [D / 'postowner-name-binding-unsigned.json', D / 'name-review-request-unsigned.json'] + [
        D / f'{env}-name-pending.json' for env in ('TEST', 'PROD')]
    if any(path.exists() for path in outputs):
        raise FileExistsError('post-owner name output already exists')
    test, test_sha = read('TEST')
    prod, prod_sha = read('PROD')
    result = bind(test, prod, {'TEST': test_sha, 'PROD': prod_sha})
    bound_at = datetime.now(timezone.utc).isoformat()
    artifacts = {'TEST': build_name_artifacts('TEST', test, test_sha, result, bound_at),
                 'PROD': build_name_artifacts('PROD', prod, prod_sha, result, bound_at)}
    request = {'status': 'pending_independent_root_name_review',
               'producer_id': PRODUCER_ID, 'producer_model': PRODUCER_MODEL,
               'produced_at': bound_at, 'raw_owners': 122, 'proposed_name_cells': 610,
               'source_matrix_canonical_sha256': result['source_matrix_canonical_sha256'],
               'owner_manifest_canonical_sha256': result['owner_manifest_canonical_sha256'],
               'postowner_capture_file_sha256': result['postowner_capture_file_sha256'],
               'pending_artifact_canonical_sha256': {env: canonical_sha256(artifact)
                                                     for env, artifact in artifacts.items()},
               'approval': None}
    for env, artifact in artifacts.items():
        (D / f'{env}-name-pending.json').write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n')
    outputs[0].write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    outputs[1].write_text(json.dumps(request, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'raw_owners': 122, 'proposed_name_cells': 610,
                      'canonical_sha256': canonical_sha256(result),
                      'pending_artifact_sha256': {env: canonical_sha256(artifact)
                                                  for env, artifact in artifacts.items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
