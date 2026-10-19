import gzip
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuPlayerName
from katrain.web.kifu.identity import _approved_names, _qualified_name_rows
from katrain.web.kifu.name_batch import _image
from katrain.web.kifu.name_evidence import registry_sha256

p = Path('/work')
env, phase = sys.argv[1:]
bundle_path = p / f'{env}-mixed20-unsigned-bundle.json.gz'
bundle = json.loads(gzip.decompress(bundle_path.read_bytes()))
approval = json.loads((p / 'root-mixed20-execution-approval.json').read_text())
sha = registry_sha256(bundle)
assert approval['hashes'][env] == sha and approval['reviewer_id'] == '/root'
ids = [c['owner']['id'] for c in bundle['candidates']]
targets = {(c['owner']['id'], c['lang']) for c in bundle['candidates']}
assert len(ids) == len(set(ids)) == len(targets) == 20
assert sum(c['lang'] == 'tw' for c in bundle['candidates']) == 17
assert sum(c['lang'] == 'ko' for c in bundle['candidates']) == 3
if phase in ('dry-run', 'apply'):
    from scripts.kifu_name_batch import main
    sys.exit(main([phase, '--bundle', str(bundle_path),
                   '--registry', str(p / f'{env}-mixed20-source-registry.json'),
                   '--inventory', str(p / f'{env}-mixed20-inventory.json.gz'),
                   '--evidence', str(p / f'{env}-mixed20-evidence.jsonl'),
                   '--database-url', os.environ['KATRAIN_DATABASE_URL'],
                   '--expected-bundle-sha256', sha]))

engine = create_engine(os.environ['KATRAIN_DATABASE_URL'])
with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
    with conn.begin():
        conn.execute(text('SET TRANSACTION READ ONLY'))
        with Session(bind=conn) as db:
            names = db.query(KifuPlayerName).filter(KifuPlayerName.player_id.in_(ids)).order_by(KifuPlayerName.id).all()
            old = {str(n.id): registry_sha256(_image(conn, KifuPlayerName.__table__, n.id))
                   for n in names if (n.player_id, n.lang) not in targets}
            scope = conn.execute(text('SELECT id,black_player_id,white_player_id,black_rank,white_rank,player_black,player_white,event,event_id,md5(sgf_content) AS sgf_md5 FROM kifu_albums WHERE black_player_id=ANY(:ids) OR white_player_id=ANY(:ids) ORDER BY id'), {'ids': ids}).mappings().all()
            scope_sha = registry_sha256([dict(r) for r in scope])
            qualified_rows = _qualified_name_rows(db, _approved_names(db, KifuPlayerName, 'player_id', ids), KifuPlayerName, 'player_id')
            qualified = {(n.player_id, n.lang): n for n, evidence in qualified_rows}
            qualified_old = sorted([[owner, lang] for owner, lang in qualified if (owner, lang) not in targets])
            complete = sorted(pid for pid in ids if {'cn', 'tw', 'jp', 'ko', 'en'} <= {lang for owner, lang in qualified if owner == pid})
            if phase == 'baseline':
                assert not any(key in qualified for key in targets)
                before_targets = {f'{pid}:{lang}': next((_image(conn, KifuPlayerName.__table__, n.id) for n in names if n.player_id == pid and n.lang == lang), None) for pid, lang in targets}
                for candidate in bundle['candidates']:
                    key = f"{candidate['owner']['id']}:{candidate['lang']}"
                    before = before_targets[key]
                    assert candidate['name_preimage_sha256'] == (registry_sha256(before) if before is not None else None)
                result = {'environment': env, 'phase': phase, 'bundle_sha256': sha,
                          'existing_names': old, 'old_target_preimages': before_targets,
                          'qualified_old_keys': qualified_old, 'scope_sha256': scope_sha,
                          'album_count': len(scope), 'five_language_complete_player_ids': complete}
            elif phase == 'verify':
                baseline = json.loads((p / f'{env}-baseline.json').read_text())
                assert old == baseline['existing_names'] and scope_sha == baseline['scope_sha256']
                assert qualified_old == baseline['qualified_old_keys']
                for candidate in bundle['candidates']:
                    name = qualified[(candidate['owner']['id'], candidate['lang'])]
                    assert name.display_name == candidate['display_name'] and name.decision_kind == 'generated'
                result = {'environment': env, 'phase': phase, 'bundle_sha256': sha,
                          'verified_name_count': 20, 'existing_names_unchanged_count': len(old),
                          'qualified_old_unchanged_count': len(qualified_old), 'read_qualified_count': len(qualified),
                          'five_language_complete_player_ids': complete,
                          'complete_players_delta': len(complete) - len(baseline['five_language_complete_player_ids']),
                          'scope_sha256': scope_sha, 'album_count': len(scope), 'passed': True}
            else:
                raise SystemExit('invalid phase')
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
