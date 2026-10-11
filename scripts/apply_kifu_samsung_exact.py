"""Frozen Samsung identity links; standalone remote runner, no catalog creation."""
import hashlib
import json
import os
from sqlalchemy import create_engine, text


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def snapshot(conn, scope):
    name = '三星杯世界围棋大师赛'
    events = [dict(x) for x in conn.execute(text('SELECT id,canonical_name FROM kifu_events WHERE canonical_name=:n ORDER BY id'), {'n': name}).mappings()]
    if len(events) != 1:
        raise ValueError('canonical event missing or ambiguous')
    event_id = events[0]['id']
    editions = [dict(x) for x in conn.execute(text('SELECT id,event_id,edition_number,edition_label,year,season FROM kifu_event_editions WHERE event_id=:e ORDER BY id'), {'e': event_id}).mappings()]
    by_number = {x['edition_number']: x['id'] for x in editions}
    if len(editions) != 30 or set(by_number) != set(range(1, 31)):
        raise ValueError('expected exactly 30 existing editions')
    if any(x['year'] is not None or x['season'] is not None or x['edition_label'] is not None for x in editions):
        raise ValueError('edition metadata changed')
    aliases = [dict(x) for x in conn.execute(text('SELECT id,event_id,alias,normalized_alias FROM kifu_event_aliases WHERE event_id=:e ORDER BY id'), {'e': event_id}).mappings()]
    if len(aliases) != 6:
        raise ValueError('expected six existing aliases')
    ids = [x[0] for x in scope['albums']] + [x['id'] for x in scope['holds']]
    rows = [dict(x) for x in conn.execute(text('SELECT id,event,date_played,event_id,event_edition_id,source_path,duplicate_of_id FROM kifu_albums WHERE id = ANY(:ids) ORDER BY id'), {'ids': ids}).mappings()]
    indexed = {x['id']: x for x in rows}
    if len(indexed) != len(ids):
        raise ValueError('scope missing or duplicate IDs')
    albums = []
    for approved in scope['albums']:
        current = indexed[approved[0]]
        fields = [current[k] for k in ['id','event','date_played','event_id','event_edition_id','source_path','duplicate_of_id']]
        if fields != approved[:7]:
            raise ValueError('approved album preimage changed: %s' % approved[0])
        pair = approved[8]
        albums.append({**current, 'target_event_id': event_id, 'target_edition_id': by_number[pair[1]] if pair else None})
    holds = [indexed[x['id']] for x in scope['holds']]
    if holds != scope['holds']:
        raise ValueError('training hold preimage changed')
    return {'database': conn.scalar(text('SELECT current_database()')), 'events': events, 'editions': editions, 'aliases': aliases, 'albums': albums, 'holds': holds}


def execute(payload):
    mode, scope = payload['mode'], payload['scope']
    if mode not in {'capture', 'dry', 'apply'}:
        raise ValueError('unsupported mode')
    if digest(scope['albums']) != '81ec9f4131ca0e2d516348782e143ba1c1012fe6a5312379765349e4aef78a3f':
        raise ValueError('approval scope digest mismatch')
    engine = create_engine(os.environ['KATRAIN_DATABASE_URL'])
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            if mode == 'capture':
                conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
                plan = snapshot(conn, scope)
                plan.update(version=1, approved_scope_sha256=digest(scope['albums']))
                plan['sha256'] = digest(plan)
                tx.rollback()
                return plan
            plan = payload['plan']
            if digest({k:v for k,v in plan.items() if k != 'sha256'}) != plan['sha256']:
                raise ValueError('plan digest mismatch')
            if mode == 'apply' and payload.get('approved_sha256') != plan['sha256']:
                raise ValueError('approval digest missing')
            conn.execute(text('LOCK TABLE kifu_albums,kifu_events,kifu_event_editions,kifu_event_aliases IN SHARE ROW EXCLUSIVE MODE'))
            live = snapshot(conn, scope)
            if live != {k:v for k,v in plan.items() if k not in ['version','sha256','approved_scope_sha256']}:
                raise ValueError('frozen catalog/database/preimages changed')
            protected_before = conn.scalar(text("SELECT md5(string_agg((to_jsonb(a)-'event_id'-'event_edition_id')::text, '' ORDER BY id)) FROM kifu_albums a WHERE id=ANY(:ids)"), {'ids':[x['id'] for x in plan['albums']]+[x['id'] for x in plan['holds']]})
            for row in plan['albums']:
                result = conn.execute(text('''UPDATE kifu_albums SET event_id=:target_event_id,event_edition_id=:target_edition_id
                    WHERE id=:id AND event IS NOT DISTINCT FROM :event AND date_played IS NOT DISTINCT FROM :date_played
                    AND source_path IS NOT DISTINCT FROM :source_path AND duplicate_of_id IS NOT DISTINCT FROM :duplicate_of_id
                    AND event_id IS NOT DISTINCT FROM :event_id AND event_edition_id IS NOT DISTINCT FROM :event_edition_id'''), row)
                if result.rowcount != 1:
                    raise ValueError('CAS failure: %s' % row['id'])
            after_links = {x['id']:(x['event_id'],x['event_edition_id']) for x in conn.execute(text('SELECT id,event_id,event_edition_id FROM kifu_albums WHERE id=ANY(:ids)'), {'ids':[x['id'] for x in plan['albums']]+[x['id'] for x in plan['holds']]}).mappings()}
            for row in plan['albums']:
                if after_links[row['id']] != (row['target_event_id'],row['target_edition_id']):
                    raise ValueError('postimage mismatch')
            for row in plan['holds']:
                if after_links[row['id']] != (row['event_id'],row['event_edition_id']):
                    raise ValueError('training hold changed')
            protected_after = conn.scalar(text("SELECT md5(string_agg((to_jsonb(a)-'event_id'-'event_edition_id')::text, '' ORDER BY id)) FROM kifu_albums a WHERE id=ANY(:ids)"), {'ids':[x['id'] for x in plan['albums']]+[x['id'] for x in plan['holds']]})
            if protected_before != protected_after:
                raise ValueError('protected album metadata changed')
            if mode == 'apply':
                tx.commit()
            else:
                tx.rollback()
            return {'database':plan['database'], 'mode':mode, 'updated_albums':len(plan['albums']), 'edition_links':sum(x['target_edition_id'] is not None for x in plan['albums']), 'training_holds':len(plan['holds']), 'protected_fields_unchanged':True, 'plan_sha256':plan['sha256'], 'committed':mode=='apply'}
        except BaseException:
            if tx.is_active:
                tx.rollback()
            raise
    engine.dispose()


if __name__ == '__main__':
    import sys
    print(json.dumps(execute(json.load(sys.stdin)), ensure_ascii=False, sort_keys=True))
