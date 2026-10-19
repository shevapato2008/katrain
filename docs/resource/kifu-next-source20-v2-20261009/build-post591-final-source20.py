"""Keep old captured packet immutable; replace held 339 with sourced 696."""
import datetime
import gzip
import hashlib
import json
from pathlib import Path

D = Path(__file__).parent
original_path = D / 'source20-v2.json'
original = json.loads(original_path.read_text())
sources = json.loads((D / '696-actual-korean-sources.json').read_text())
assert len(sources) == 2 and all(s['http_status'] == 200 and s['method'] == 'GET' for s in sources)
for item in sources:
    assert hashlib.sha256((D / item['body_file']).read_bytes()).hexdigest() == item['body_sha256']
rows = [row for row in original['players'] if row['prod_player_id'] != 339]
assert len(rows) == 19
rows.append({
    'prod_player_id': 696, 'test_player_id': 697,
    'linked_slots_per_environment': 25,
    'missing_language': 'ko',
    'existing_qualified_names': {'cn': '高若环', 'en': 'Gao Ruohuan',
                                 'jp': '高若环', 'tw': '高若環'},
    'source_only': True, 'no_owner_binding_or_approval': True,
    'proposed_name': '가오뤄환',
    'evidence_kind': 'direct_korean_go_official_opponent_and_specialist_news',
    'source_quality': 'Korea Baduk Association official opponent row and Cyberoro specialist Go reporting both publish the complete Hangul name. An older TV Baduk bracket has a wrong last Hanzi and is not used as an original-name anchor.',
    'identity_note': 'Chinese woman Go professional of first dan in Cyberoro report; official Korean Go game result uses the same Hangul name. Exact original 高若环, existing four qualified names and 25 linked games require final root same-person review.',
    'sources': sources,
    'review_flag': 'replace_unqualified_legacy_review_고_약환',
})
assert len(rows) == len({r['prod_player_id'] for r in rows}) == 20
result = {
    'packet_kind': 'post591_source_only_pending_final20',
    'produced_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'based_on_immutable_source_packet': 'source20-v2.json',
    'based_on_immutable_source_packet_file_sha256': hashlib.sha256(original_path.read_bytes()).hexdigest(),
    'replaced_held_owner': {'prod_player_id': 339, 'test_player_id': 340,
                            'reason': 'Japanese official reading チン ハクショウ maps to 친 하쿠쇼 under current NIKL JA-to-KO rule, while Korean Jstart article directly publishes 진 하쿠쇼 at reference tier. Do not claim them equivalent or force conventional gate.'},
    'source_registry_proposal': 'source-registry-proposed-pending.json',
    'source_registry_status': 'pending_root_review',
    'current591_readonly_capture': {
        'original_19': ['PROD-current591-exact20-readonly.json.gz', 'TEST-current591-exact20-readonly.json.gz'],
        'replacement_696': ['PROD-replacement696-current591-readonly.json.gz', 'TEST-replacement696-current591-readonly.json.gz'],
    },
    'players': rows,
    'scope': {'distinct_players': 20, 'linked_slots_per_environment': sum(r['linked_slots_per_environment'] for r in rows)},
    'status': 'unsigned_pending_source_identity_rule_review',
}
path = D / 'source20-post591-final-pending.json'
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print('final pending source owners', len(rows), 'slots', result['scope']['linked_slots_per_environment'],
      'sha256', hashlib.sha256(path.read_bytes()).hexdigest())
