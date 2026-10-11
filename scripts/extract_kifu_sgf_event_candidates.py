#!/usr/bin/env python3
"""Read-only extraction of supplemental SGF event context. No approval or DB mutations."""
import argparse
from collections import Counter
import datetime
import hashlib
import json
import os
import re
import sys
import time

from katrain.core.sgf_parser import SGF
try:
    from katrain.web.kifu.name_structure import RULE_VERSION, structure_event
except ModuleNotFoundError:
    # Production may predate the structural helper; defer comparisons to local enrichment.
    RULE_VERSION, structure_event = "deferred_to_local", None

SQL = """SELECT a.id AS album_id, a.event AS album_event, a.sgf_content,
       a.source_path, r.id AS raw_event_id, r.parsed_data->>'series_core' AS series_core
FROM kifu_albums a JOIN kifu_raw_event_values r ON r.raw_value = a.event
WHERE a.event_id IS NULL AND r.category = 'unclassified_pending' AND a.id > :after_id
ORDER BY a.id LIMIT :limit"""


def root_fragment(sgf):
    """Clip after the root, respecting escaped brackets, semicolons and parentheses."""
    start = sgf.find('(')
    if start < 0:
        raise ValueError('missing collection')
    inside = escaped = seen_node = False
    for i in range(start + 1, len(sgf)):
        ch = sgf[i]
        if inside:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == ']':
                inside = False
        elif ch == '[':
            inside = True
        elif ch == ';':
            if seen_node:
                return sgf[start:i] + ')'
            seen_node = True
        elif ch in '()':
            if seen_node:
                return sgf[start:i] + ')'
    raise ValueError('unterminated root')


def extract(row):
    text = row['sgf_content']
    props = dict(SGF.parse_sgf(root_fragment(text)).properties)
    raw = row['album_event']
    candidates = {}
    def add(value, source):
        value = value.strip()
        if not value or value == (raw or '').strip():
            return
        if value not in candidates:
            structured = structure_event(value) if structure_event else None
            candidates[value] = {'value': value, 'sources': [], 'candidate_core': structured['core'] if structured else None,
                'structure': structured, 'core_differs': structured['core'] != row['series_core'] if structured else None,
                'needs_manual_review': True}
        candidates[value]['sources'].append(source)
    for i, value in enumerate(props.get('GN', [])[1:], 1):
        add(value, f'GN[{i}]')
    for i, value in enumerate(props.get('GC', [])):
        # Only strip the known golaxy result suffix. General comments remain review text.
        label = re.split(r'\s*\|\s*(?:结果|result)\s*:', value, maxsplit=1, flags=re.I)[0]
        add(label, f'GC[{i}]')
    return {key: value for key, value in row.items() if key != 'sgf_content'} | {
        'sgf_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'root_properties': {k: props.get(k, []) for k in ('EV', 'GN', 'GC', 'DT', 'RO', 'PB', 'PW', 'RE', 'SO')},
        'candidate_count': len(candidates), 'candidates': list(candidates.values()),
        'core_comparison_deferred': structure_event is None,
        'root_EV_differs': any(value != raw for value in props.get('EV', [])),
        'decision': 'UNREVIEWED; extraction only',
    }


def emit(value):
    print(json.dumps(value, ensure_ascii=False, separators=(',', ':')), flush=True)


def main():
    from sqlalchemy import create_engine, text
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--after-id', type=int, default=0)
    parser.add_argument('--batch-size', type=int, default=250)
    parser.add_argument('--pause-ms', type=int, default=50)
    args = parser.parse_args()
    if min(args.limit, args.batch_size) < 1 or min(args.after_id, args.pause_ms) < 0:
        parser.error('limit/batch-size must be positive; after-id/pause-ms nonnegative')
    started = time.monotonic()
    engine = create_engine(os.environ['KATRAIN_DATABASE_URL'], pool_pre_ping=True)
    counts = Counter()
    candidate_counts = Counter()
    last_id = args.after_id
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        connection.execute(text("SET LOCAL statement_timeout = '120s'"))
        connection.execute(text("SET LOCAL lock_timeout = '2s'"))
        meta = dict(connection.execute(text("SELECT current_setting('transaction_read_only') AS read_only, "
            "txid_current_snapshot()::text AS snapshot, clock_timestamp()::text AS captured_at")).mappings().one())
        if meta['read_only'] != 'on':
            raise RuntimeError('read-only transaction required')
        emit({'kind': 'manifest', 'format': 'kifu-sgf-event-candidates-v1', 'meta': meta,
              'sql': SQL, 'parameters': vars(args), 'structure_rule_version': RULE_VERSION,
              'database_writes': 0, 'approval_decisions': 0, 'translations': 0,
              'capture_started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        try:
            query = connection.execution_options(stream_results=True, yield_per=args.batch_size).execute(
                text(SQL), {'after_id': args.after_id, 'limit': args.limit})
            for item in query.mappings():
                row = dict(item)
                last_id = row['album_id']
                counts['scanned'] += 1
                try:
                    value = extract(row)
                    counts['parse_ok'] += 1
                    counts['root_EV_present'] += bool(value['root_properties']['EV'])
                    counts['multiple_GN'] += len(value['root_properties']['GN']) > 1
                    counts['with_supplemental_candidate'] += bool(value['candidates'])
                    counts['core_comparison_deferred_games'] += value['core_comparison_deferred']
                    counts['core_differs_games'] += any(c['core_differs'] for c in value['candidates'])
                    counts['root_EV_differs_games'] += value['root_EV_differs']
                    counts['candidate_values'] += len(value['candidates'])
                    for candidate in value['candidates']:
                        candidate_counts[candidate['value']] += 1
                    emit({'kind': 'album', **value})
                except Exception as error:
                    counts['parse_error'] += 1
                    emit({'kind': 'parse_error', 'album_id': last_id,
                          'error_type': type(error).__name__, 'sgf_sha256': hashlib.sha256(row['sgf_content'].encode()).hexdigest()})
                if counts['scanned'] % args.batch_size == 0 and args.pause_ms:
                    time.sleep(args.pause_ms / 1000)
            query.close()
        finally:
            connection.rollback()
    engine.dispose()
    emit({'kind': 'summary', 'counts': dict(counts), 'candidate_distinct': len(candidate_counts),
          'top_candidates': candidate_counts.most_common(100), 'last_album_id': last_id,
          'wall_clock_seconds': round(time.monotonic() - started, 3), 'transaction_end': 'ROLLBACK',
          'database_writes': 0, 'complete': True})


if __name__ == '__main__':
    main()
