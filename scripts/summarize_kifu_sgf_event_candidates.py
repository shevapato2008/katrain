#!/usr/bin/env python3
"""Enrich captured JSONL locally; write unreviewed candidates and conflict aggregates."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import io
from pathlib import Path

from katrain.web.kifu.name_structure import RULE_VERSION, structure_event


def summarize(source, output, report_path):
    counts = Counter()
    grouped = Counter()
    changed_cores = Counter()
    manifest = summary = None
    previous = 0
    opener = gzip.open if str(source).endswith('.gz') else open
    with opener(source, 'rt', encoding='utf-8') as infile, open(output, 'wb') as rawout, \
            gzip.GzipFile(filename='', fileobj=rawout, mode='wb', mtime=0) as compressed, \
            io.TextIOWrapper(compressed, encoding='utf-8') as outfile:
        for line in infile:
            row = json.loads(line)
            if row['kind'] == 'manifest':
                if manifest is not None or row['meta']['read_only'] != 'on':
                    raise ValueError('one read-only manifest required')
                manifest = row
            elif row['kind'] in {'album', 'parse_error'}:
                if manifest is None or row['album_id'] <= previous:
                    raise ValueError('ordered unique IDs and manifest required')
                previous = row['album_id']
                counts['scanned'] += 1
                if row['kind'] == 'parse_error':
                    counts['parse_error'] += 1
                else:
                    counts['parse_ok'] += 1
                    counts['root_EV_present'] += bool(row['root_properties']['EV'])
                    counts['multiple_GN'] += len(row['root_properties']['GN']) > 1
                    counts['with_supplemental_candidate'] += bool(row['candidates'])
                    for candidate in row['candidates']:
                        structured = structure_event(candidate['value'])
                        candidate.update(structure=structured, candidate_core=structured['core'],
                                         core_differs=structured['core'] != row['series_core'])
                        grouped[candidate['value']] += 1
                        if candidate['core_differs']:
                            changed_cores[(row['series_core'], candidate['candidate_core'])] += 1
                    row['core_comparison_deferred'] = False
                    row['local_structure_rule_version'] = RULE_VERSION
                    counts['candidate_values'] += len(row['candidates'])
                    counts['core_differs_games'] += any(c['core_differs'] for c in row['candidates'])
                    counts['root_EV_differs_games'] += row['root_EV_differs']
            elif row['kind'] == 'summary':
                summary = row
                row = row | {'counts': dict(counts), 'capture_counts': row['counts'],
                             'local_structure_rule_version': RULE_VERSION}
            outfile.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
    if not summary or not summary['complete'] or summary['counts']['scanned'] != counts['scanned']:
        raise ValueError('incomplete capture; no complete report issued')
    if summary['transaction_end'] != 'ROLLBACK' or summary['database_writes'] != 0:
        raise ValueError('capture must be read-only and rolled back')
    digest = hashlib.sha256()
    with open(source, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    report = {'format': 'kifu-sgf-event-supplemental-report-v1', 'manifest': manifest,
              'source_artifact': str(source), 'source_sha256': digest.hexdigest(),
              'enriched_artifact': str(output), 'local_rule_version': RULE_VERSION,
              'counts': dict(counts), 'capture_summary': summary,
              'candidate_distinct': len(grouped),
              'candidate_groups': [{'value': v, 'games': n} for v, n in grouped.most_common()],
              'core_difference_groups': [{'album_event_core': a, 'candidate_core': c, 'games': n}
                                         for (a, c), n in changed_cores.most_common()],
              'approval_decisions': 0, 'database_writes': 0, 'translations': 0,
              'interpretation': 'Exact string/component differences are research conflicts, not identity contradictions. '
                  'GN/GC originate from same stored SGF and do not establish independent evidence or safe dedup.'}
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source')
    p.add_argument('output')
    p.add_argument('report')
    args = p.parse_args()
    result = summarize(args.source, args.output, args.report)
    print(json.dumps({'counts': result['counts'], 'candidate_distinct': result['candidate_distinct']}, ensure_ascii=False))
