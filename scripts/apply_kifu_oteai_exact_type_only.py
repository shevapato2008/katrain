"""Freeze/check/apply independently approved Oteai IDs with exact type-only CAS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from sqlalchemy import create_engine, text

APPROVED_ALLOWLIST_SHA = 'edd2640dfb81619fe836cb88290f5a2c5442764bb2d69ff80e3fdfc572c43772'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def freeze_plan(scope, rows, held_rows, target_id, environment):
    if digest(scope['exact_raw_allowlist']) != scope['allowlist_sha256']:
        raise ValueError('allowlist hash differs')
    approved = {r[0]: r for r in scope['album_preimages']}
    if len(approved) != len(scope['album_preimages']):
        raise ValueError('duplicate approved IDs')
    if not rows or len({r[0] for r in rows}) != len(rows):
        raise ValueError('empty or duplicate selected IDs')
    extra = sorted({r[0] for r in rows} - set(approved))
    if extra:
        raise ValueError(f'unapproved album IDs need separate review: {extra}')
    for row in rows:
        if row != approved[row[0]]:
            raise ValueError(f'approved preimage differs: {row[0]}')
    if environment == 'prod' and sorted(rows) != sorted(scope['album_preimages']):
        raise ValueError('PROD approved set differs')
    plan = {'version': 1, 'environment': environment, 'allowlist_sha256': scope['allowlist_sha256'],
            'target_event_id': target_id, 'target_canonical_name': '大手合',
            'approved_raws': sorted(r['raw_event'] for r in scope['exact_raw_allowlist']),
            'rows': sorted(rows), 'held_rows': sorted(held_rows),
            'missing_approved_ids': sorted(set(approved) - {r[0] for r in rows})}
    plan['sha256'] = digest(plan)
    return plan


def read_rows(db, raws):
    return [list(r) for r in db.execute(text(
        'SELECT id,event,date_played,event_id,event_edition_id FROM kifu_albums '
        'WHERE event = ANY(:raws) ORDER BY id'), {'raws': list(raws)})]


def run(engine, plan, apply=False, approved_sha256=None):
    if digest({k:v for k,v in plan.items() if k != 'sha256'}) != plan['sha256']:
        raise ValueError('plan hash differs')
    if plan['allowlist_sha256'] != APPROVED_ALLOWLIST_SHA:
        raise ValueError('independent approved allowlist differs')
    if not plan['rows'] or len({r[0] for r in plan['rows']}) != len(plan['rows']):
        raise ValueError('empty or duplicate selected IDs')
    if apply and approved_sha256 != plan['sha256']:
        raise ValueError('approved plan hash differs')
    with engine.begin() as db:
        if apply:
            db.execute(text('LOCK TABLE kifu_albums, kifu_events IN SHARE ROW EXCLUSIVE MODE'))
        else:
            db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        name = db.execute(text('SELECT canonical_name FROM kifu_events WHERE id=:id'),
                          {'id': plan['target_event_id']}).scalar_one()
        if name != plan['target_canonical_name']:
            raise ValueError('target event identity differs')
        rows = read_rows(db, plan['approved_raws'])
        if rows != plan['rows']:
            raise ValueError('live exact null preimages differ')
        if any(r[3] is not None or r[4] is not None for r in plan['rows']):
            raise ValueError('plan must contain null links only')
        held_ids = [r[0] for r in plan['held_rows']]
        held = [list(r) for r in db.execute(text(
            'SELECT id,event,date_played,event_id,event_edition_id FROM kifu_albums WHERE id=ANY(:ids) ORDER BY id'),
            {'ids': held_ids})] if held_ids else []
        if held != plan['held_rows']:
            raise ValueError('held preimages differ')
        if apply:
            for id_, raw, date, _, _ in plan['rows']:
                result = db.execute(text('UPDATE kifu_albums SET event_id=:target WHERE id=:id '
                    'AND event IS NOT DISTINCT FROM :raw AND date_played IS NOT DISTINCT FROM :date '
                    'AND event_id IS NULL AND event_edition_id IS NULL'),
                    {'target':plan['target_event_id'], 'id':id_, 'raw':raw, 'date':date})
                if result.rowcount != 1:
                    raise ValueError(f'CAS failed: {id_}')
            expected = [[id_, raw, date, plan['target_event_id'], None]
                        for id_, raw, date, _, _ in plan['rows']]
            if read_rows(db, plan['approved_raws']) != expected:
                raise ValueError('postwrite approved rows differ')
            after_held = [list(r) for r in db.execute(text(
                'SELECT id,event,date_played,event_id,event_edition_id FROM kifu_albums '
                'WHERE id=ANY(:ids) ORDER BY id'), {'ids': held_ids})] if held_ids else []
            if after_held != plan['held_rows']:
                raise ValueError('postwrite held rows differ')
        return {'plan_sha256':plan['sha256'], 'mode':'apply' if apply else 'dry_run',
                'matched_albums':len(plan['rows']), 'held_albums':len(held),
                'target_event_id':plan['target_event_id'], 'updated_albums':len(plan['rows']) if apply else 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--database-url', default=os.getenv('KATRAIN_DATABASE_URL'))
    p.add_argument('--apply', action='store_true')
    p.add_argument('--approved-plan-sha256')
    a = p.parse_args()
    engine = create_engine(a.database_url)
    try:
        print(json.dumps(run(engine, json.loads(a.plan.read_text()), a.apply, a.approved_plan_sha256), ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
