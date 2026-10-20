#!/usr/bin/env python3
"""Resume GPT-only whole-page/whole-figure recognition without changing first100.

No database writes, OCR, CV, model fallback, replay fabrication, or credential reads.
All stages are resumable; only validated successes are cached. ``all`` also emits
partial results/coverage when a bounded request fails. Run it again to retry failures.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from urllib.parse import quote

from PIL import Image

COLLECTION = Path('/Users/fan/Repositories/go-topic-collections')
DEFAULT_BOOK = COLLECTION / 'curriculum/13_形势判断与胜负策略/围棋形势判断基础_石田芳夫_1983'
DEFAULT_OLD = COLLECTION / 'curriculum/recognition-comparison/ishida-first100'
DEFAULT_OUTPUT = COLLECTION / 'curriculum/recognition-comparison/ishida-full195'
MODEL, REASONING = 'gpt-6.1-sol', 'high'
CODEX = '/Users/fan/.hermes/node/bin/codex'
FROZEN_FILES = ('results.json', 'manifest.json', 'audit.json', 'run.py', 'source.json')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def legacy_module(old=DEFAULT_OLD):
    spec = importlib.util.spec_from_file_location('frozen_ishida_first100', Path(old) / 'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Reuse the approved whole-figure transcription contract and coordinate conversion.
LEGACY = legacy_module()
BOARD_SCHEMA = deepcopy(LEGACY.BOARD_SCHEMA)
obj, arr, STRING, INTEGER = LEGACY.obj, LEGACY.arr, LEGACY.STRING, LEGACY.INTEGER
BOX = dict(type='array', items=dict(type='integer', minimum=0, maximum=1000), minItems=4, maxItems=4)
DETECTION_SCHEMA = obj(dict(pages=arr(obj(dict(
    id=STRING, figures=arr(obj(dict(label=STRING, ref_index=INTEGER,
        grid_bbox=BOX, input_bbox=BOX, caption=STRING, notes=STRING))),
    unrepresented_references=arr(obj(dict(ref_index=INTEGER, reason=STRING))), notes=STRING)))))


def check_schema(value, schema, at='response'):
    """Validate the fixed CLI schema again before trusting a response/cache."""
    kind = schema.get('type')
    valid = {'object': isinstance(value, dict), 'array': isinstance(value, list),
             'string': isinstance(value, str), 'integer': type(value) is int,
             'number': type(value) in (int, float)}
    if not valid.get(kind, True):
        raise ValueError(f'{at}: expected {kind}')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{at}: unexpected enum value')
    if kind == 'object':
        if set(schema.get('required', [])) - set(value):
            raise ValueError(f'{at}: missing fields')
        if schema.get('additionalProperties') is False and set(value) - set(schema['properties']):
            raise ValueError(f'{at}: unexpected fields')
        for key, item in value.items():
            if key in schema.get('properties', {}):
                check_schema(item, schema['properties'][key], f'{at}.{key}')
    elif kind == 'array':
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', float('inf')):
            raise ValueError(f'{at}: wrong item count')
        for index, item in enumerate(value):
            check_schema(item, schema['items'], f'{at}[{index}]')
    elif kind in ('integer', 'number'):
        if not schema.get('minimum', -float('inf')) <= value <= schema.get('maximum', float('inf')):
            raise ValueError(f'{at}: out of range')


def convert_new(board):
    check_schema({'figures': [board]}, BOARD_SCHEMA)
    result = LEGACY.convert({}, board)
    if result['issues']:
        raise ValueError('; '.join(result['issues']))
    if not 0 <= board['origin_confidence'] <= 1:
        raise ValueError('origin confidence outside 0..1')
    # No chronological claim follows from numbers printed in a final position.
    result.update(coordinate_space='full_board_zero_based', replay_status='pending',
                  replay_reason='Static transcription only; no independently sourced initial setup and ordered history.')
    return result


def validate_response(value, root, ids, schema):
    check_schema(value, schema)
    actual = [item['id'] for item in value[root]]
    if len(actual) != len(set(actual)) or set(actual) != set(ids):
        raise ValueError('missing/duplicate/unexpected response IDs')
    if root == 'figures':
        for board in value[root]:
            convert_new(board)
    else:
        for page in value[root]:
            for figure in page['figures']:
                grid, box = figure['grid_bbox'], figure['input_bbox']
                if not (grid[0] < grid[2] and grid[1] < grid[3] and
                        box[0] <= grid[0] < grid[2] <= box[2] and
                        box[1] <= grid[1] < grid[3] <= box[3]):
                    raise ValueError('invalid grid/input box containment')
                if figure['ref_index'] < 0:
                    raise ValueError('negative reference index')


def cache_key(prompt, schema, images, reasoning=REASONING):
    return canonical_hash(dict(model=MODEL, reasoning=reasoning, prompt=prompt, schema=schema, images=images))


def merge_figures(old, new):
    if len({f['id'] for f in old + new}) != len(old) + len(new):
        raise ValueError('duplicate physical recognition ID')
    return deepcopy(old) + new


def coverage_report(pages, figures):
    by_page = defaultdict(list)
    for figure in figures:
        by_page[figure['page']].append(figure)
    report = dict(baseline_references=0, covered_references=0, references=[], missing=[], extras=[], splits=[])
    for page in pages:
        matches = defaultdict(list)
        for figure in by_page[page['page']]:
            index = figure['ref_index']
            if index:
                matches[index].append(figure['id'])
            else:
                report['extras'].append(dict(page=page['page'], figure_id=figure['id'],
                    reason=figure.get('detection_notes') or 'Unlisted physical diagram, retained independently.'))
        reasons = {item['ref_index']: item['reason'] for item in page.get('unrepresented_references', [])}
        for index, reference in enumerate(page['references'], 1):
            ids = matches[index]
            record = dict(page=page['page'], ref_index=index, label=reference.get('label', ''),
                source_pointer=(page.get('reference_pointers') or [None] * len(page['references']))[index - 1],
                figure_ids=ids, status='covered' if ids else 'missing',
                reason='' if ids else reasons.get(index, page.get('detection_error') or page.get('detection_notes') or 'Detection not complete.'))
            report['baseline_references'] += 1
            report['covered_references'] += bool(ids)
            report['references'].append(record)
            if not ids:
                report['missing'].append(record)
            if len(ids) > 1:
                report['splits'].append(record)
    return report


def recognition_inputs(figures, output):
    images, context = [], []
    # Every figure receives its complete caption crop AND its full original page.
    for figure in figures:
        images.append(dict(id=figure['id'] + ':diagram-with-caption', image=str(output / figure['crop'])))
        crop_index = len(images)
        images.append(dict(id=figure['id'] + ':full-page', image=figure['input_image']))
        context.append(dict(id=figure['id'], diagram_image=crop_index, full_page_image=len(images),
            caption=figure['label'], detected_full_caption=figure.get('caption', ''),
            existing_book_json_figure_text=figure['text'], complete_parsed_page_context=figure['page_context']))
    original = LEGACY.recognition_prompt([])
    original = original.replace('Each image has one printed diagram.',
        'Each diagram_image has one target diagram plus its entire relevant caption. '
        'Its full_page_image is mandatory context: inspect all footnotes, capture/ko/recapture notes and caption continuations. '
        'Do not transcribe neighboring diagrams from a context page. Image indices are explicitly listed below.')
    original = original.removesuffix('[]')
    return images, original + json.dumps(context, ensure_ascii=False)


class Runner:
    def __init__(self, book, output, old, start=101, end=195, workers=3, timeout=600, attempts=2):
        self.book, self.output, self.old = Path(book), Path(output), Path(old)
        self.start, self.end, self.workers, self.timeout, self.attempts = start, end, workers, timeout, attempts
        if not (101 <= start <= end <= 195):
            raise ValueError('Only continuation pages101–195 are allowed; old266 must never be model inputs')
        if workers not in (1, 2, 3) or not (1 <= attempts <= 3):
            raise ValueError('workers must be1..3 and bounded attempts1..3')
        if self.output.resolve() == self.old.resolve() or self.old.resolve() in self.output.resolve().parents:
            raise ValueError('output must be separate from frozen first100')

    def old_results(self):
        result = read(self.old / 'results.json')
        if len(result['figures']) != 266 or {p['page'] for p in result['pages']} != set(range(1, 101)):
            raise ValueError('unexpected frozen first100 coverage')
        return result

    def freeze(self):
        record = dict(files={name: digest(self.old / name) for name in FROZEN_FILES},
                      final_figures_sha256=canonical_hash(self.old_results()['figures']))
        path = self.output / 'frozen-first100.json'
        if path.exists() and read(path) != record:
            raise ValueError('frozen first100 has changed since continuation preparation')
        for path_name, expected in self.old_results()['sources'].items():
            if digest(path_name) != expected:
                raise ValueError('source book/PDF hash differs from accepted first100')
        write(path, record)
        return record

    def prepare(self):
        self.freeze()
        book_path = self.book / 'output/book.json'
        book = read(book_path)
        refs, descriptions = defaultdict(list), defaultdict(list)
        def walk(value, pointer='', page=None):
            if isinstance(value, dict):
                page = value.get('page', page)
                if isinstance(page, int):
                    if value.get('type') == 'figure_ref':
                        refs[page].append((value, pointer))
                    elif value.get('type') == 'description' and value.get('text'):
                        descriptions[page].append(value['text'])
                for key, child in value.items():
                    walk(child, pointer + '/' + key.replace('~', '~0').replace('/', '~1'), page)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, pointer + '/' + str(index), page)
        walk(book)
        if sum(map(len, refs.values())) != 468:
            raise ValueError('canonical source baseline changed: expected468 figure_refs')
        pages = []
        for number in range(1, 196):
            path = self.book / 'output/pages' / f'page_{number:03d}.png'
            with Image.open(path) as image:
                width, height = image.size
            ordered = sorted(refs[number], key=lambda item: (
                int(item[0].get('bbox', {}).get('y_min', 0) * 1000) // 60,
                item[0].get('bbox', {}).get('x_min', 0)))
            pages.append(dict(page=number, id=f'p{number:03d}', input_image=str(path),
                page_sha256=digest(path), width=width, height=height,
                source=quote(os.path.relpath(path, self.output)), references=[x[0] for x in ordered],
                reference_pointers=[x[1] for x in ordered], descriptions=descriptions[number], figure_ids=[]))
        old = self.old_results()
        # Existing references must match by content and ordering before model work.
        for current, accepted in zip(pages[:100], old['pages']):
            if current['references'] != accepted['references']:
                raise ValueError('first100 canonical reference ordering changed')
        write(self.output / 'source.json', dict(title=book['title'], author=book['author'],
            translator=book.get('translator', ''), model=MODEL, reasoning=REASONING,
            pages=pages, sources=old['sources'], requested_range=[self.start, self.end],
            created=time.strftime('%Y-%m-%d %H:%M:%S %z')))
        print(json.dumps(dict(stage='prepare', full_pages=195, continuation_pages=self.end-self.start+1,
            baseline_refs=468, continuation_refs=sum(len(p['references']) for p in pages[self.start-1:self.end]),
            old_final_objects_reused=266, model=MODEL, workers=self.workers)), flush=True)

    def check_reference_indices(self, value, root):
        if root != 'pages':
            return
        source_path = self.output / 'source.json'
        if not source_path.exists():
            raise ValueError('prepare is required before page detection')
        limits = {p['id']: len(p['references']) for p in read(source_path)['pages']}
        for page in value['pages']:
            limit = limits[page['id']]
            if any(not 0 <= f['ref_index'] <= limit for f in page['figures']):
                raise ValueError('diagram reference index exceeds source checklist')
            missing = page['unrepresented_references']
            if (any(not 1 <= f['ref_index'] <= limit for f in missing) or
                    len({f['ref_index'] for f in missing}) != len(missing)):
                raise ValueError('invalid/duplicate unrepresented reference index')

    def invoke(self, kind, stem, images, prompt, schema, root, ids):
        for ident in ids:
            match = re.fullmatch(r'p(\d{3})(?:-f\d+)?', ident)
            if not match or not self.start <= int(match[1]) <= self.end:
                raise ValueError('model request outside authorized continuation range')
        schema = json.loads(json.dumps(schema))
        schema['properties'][root]['items']['properties']['id']['enum'] = ids
        hashes = [dict(id=item['id'], sha256=digest(item['image'])) for item in images]
        key = cache_key(prompt, schema, hashes)
        directory = self.output / 'raw' / kind / stem / key
        meta_path, result_path = directory / 'meta.json', directory / 'result.json'
        if meta_path.exists() and result_path.exists():
            meta = read(meta_path)
            value = read(result_path)
            validate_response(value, root, ids, schema)
            self.check_reference_indices(value, root)
            if meta.get('cache_key') == key and meta.get('result_sha256') == digest(result_path):
                return value, meta
        directory.mkdir(parents=True, exist_ok=True)
        write(directory / 'schema.json', schema)
        (directory / 'prompt.txt').write_text(prompt)
        value, metrics = self.launch(directory, images, prompt, schema, root, ids)
        validate_response(value, root, ids, schema)
        self.check_reference_indices(value, root)
        write(result_path, value)
        meta = dict(cache_key=key, model=MODEL, reasoning=REASONING,
            auth='existing ChatGPT login via Codex CLI', image_sha256=hashes,
            schema_sha256=canonical_hash(schema), prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
            result_sha256=digest(result_path), **metrics)
        write(meta_path, meta)  # final atomic success checkpoint
        return value, meta

    def launch(self, directory, images, prompt, schema, root, ids):
        command = [CODEX, 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
            '--sandbox', 'read-only', '--model', MODEL, '-c', f'model_reasoning_effort="{REASONING}"',
            '--json', '--output-schema', str(directory / 'schema.json')]
        for image in images:
            command += ['--image', str(image['image'])]
        started = time.monotonic()
        # Retain all prior attempt events, including failures, across process restarts.
        previous = len(list(directory.glob('attempt-*.events.jsonl')))
        for attempt in range(1, self.attempts + 1):
            attempt_started = time.monotonic()
            prefix = directory / f'attempt-{previous + attempt:03d}'
            answer = prefix.with_suffix('.answer.json')
            error = None
            with prefix.with_suffix('.events.jsonl').open('w') as events, prefix.with_suffix('.stderr.log').open('w') as stderr:
                try:
                    process = subprocess.Popen(command + ['-o', str(answer), '-'], stdin=subprocess.PIPE,
                        text=True, stdout=events, stderr=stderr, cwd='/tmp', start_new_session=True,
                        env={key: value for key, value in os.environ.items()
                             if key not in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL')} )
                    try:
                        process.communicate(prompt, timeout=self.timeout)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.communicate()
                        raise
                    if process.returncode or not answer.exists():
                        raise RuntimeError(f'Codex exit{process.returncode}; see {prefix.name}.stderr.log')
                    value = read(answer)
                    validate_response(value, root, ids, schema)
                    self.check_reference_indices(value, root)
                    return value, dict(attempts=previous + attempt, elapsed_seconds=round(time.monotonic()-started, 2))
                except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
                    error = f'{type(exc).__name__}: {exc}'
                finally:
                    write(prefix.with_suffix('.timing.json'), dict(elapsed_seconds=round(time.monotonic()-attempt_started, 2),
                        error=error, finished_at=time.strftime('%Y-%m-%d %H:%M:%S %z')))
            if attempt < self.attempts:
                time.sleep(3)
        raise RuntimeError(error)

    def jobs(self, stage, jobs, schema, root):
        checkpoint = dict(jobs=[], failures=[], model=MODEL)
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self.invoke, stage, job['stem'], job['images'], job['prompt'],
                       schema, root, job['ids']): job for job in jobs}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    value, meta = future.result()
                    checkpoint['jobs'].append(dict(stem=job['stem'], ids=job['ids'],
                        cache_key=meta['cache_key'], response=value))
                    print(f'{stage} {len(checkpoint["jobs"])}/{len(jobs)} complete: {",".join(job["ids"])}', flush=True)
                except Exception as error:
                    checkpoint['failures'].append(dict(ids=job['ids'], error=str(error)))
                    print(f'{stage} failed {job["ids"]}: {error}', flush=True)
                write(self.output / f'{stage}-checkpoint.json', checkpoint)
        return checkpoint

    def detect_prompt(self, pages, previous=None):
        # Preserve the former independent visual discovery method, replacing only box semantics.
        prompt = LEGACY.detect_prompt(pages, previous)
        prompt = prompt.replace('bbox is [left,top,right,bottom]', 'grid_bbox is [left,top,right,bottom]')
        prompt = prompt.replace('Each bbox must contain', 'Each grid_bbox must contain')
        prompt += ('\nAlso return input_bbox, independently from grid_bbox: it MUST contain the whole grid '
            'AND every relevant printed caption/footnote/capture/ko/recapture annotation, even below or beside the grid. '
            'It may contain surrounding prose if needed; never truncate a caption to isolate the grid. '
            'Return the entire relevant printed caption in caption, preserving all note numbers and symbols. '
            'Both boxes use normalized page0..1000 coordinates. The corresponding full page will ALWAYS accompany recognition. '
            'For any checklist reference without a physical grid, report its ref_index and specific reason in unrepresented_references. '
            'Explain unlisted diagrams and split/variation relationships in figure notes. Explicitly report zero-diagram pages.')
        return prompt

    def detect(self):
        self.freeze()
        pages = [p for p in read(self.output / 'source.json')['pages'] if self.start <= p['page'] <= self.end]
        groups = [pages[i:i+4] for i in range(0, len(pages), 4)]
        jobs = [dict(stem=f'batch-{i:03d}', ids=[p['id'] for p in group],
            images=[dict(id=p['id'], image=p['input_image']) for p in group], prompt=self.detect_prompt(group))
            for i, group in enumerate(groups)]
        checkpoint = self.jobs('detect', jobs, DETECTION_SCHEMA, 'pages')
        detected = {p['id']: p for job in checkpoint['jobs'] for p in job['response']['pages']}
        rechecks = []
        for page in pages:
            previous = detected.get(page['id'])
            if previous and set(range(1, len(page['references'])+1)) - {f['ref_index'] for f in previous['figures']}:
                rechecks.append(dict(stem=page['id'], ids=[page['id']],
                    images=[dict(id=page['id'], image=page['input_image'])], prompt=self.detect_prompt([page], [previous])))
        if rechecks:
            self.jobs('recheck', rechecks, DETECTION_SCHEMA, 'pages')
        else:
            write(self.output / 'recheck-checkpoint.json', dict(jobs=[], failures=[]))

    def crop(self):
        self.freeze()
        data = read(self.output / 'source.json')
        detected, errors = {}, {}
        for stage in ('detect', 'recheck'):
            path = self.output / f'{stage}-checkpoint.json'
            if path.exists():
                state = read(path)
                detected.update({p['id']: p for job in state['jobs'] for p in job['response']['pages']})
                errors.update({ident: f['error'] for f in state['failures'] for ident in f['ids']})
        figures = []
        for page in data['pages']:
            if not self.start <= page['page'] <= self.end:
                continue
            outcome = detected.get(page['id'])
            if not outcome:
                page.update(detection_status='failed', detection_error=errors.get(page['id'], 'Detection not run'))
                continue
            if any(f['ref_index'] > len(page['references']) for f in outcome['figures']):
                raise ValueError(f'{page["id"]}: reference index exceeds source checklist')
            page.update(detection_status='complete', detection_notes=outcome['notes'],
                unrepresented_references=outcome['unrepresented_references'], detected_count=len(outcome['figures']),
                detection_recheck_error=errors.get(page['id']))
            # Sorting uses geometry only; IDs remain independent of caption/ref_index.
            found = sorted(outcome['figures'], key=lambda f: (f['grid_bbox'][1] // 60, f['grid_bbox'][0]))
            with Image.open(page['input_image']) as image:
                for rank, located in enumerate(found, 1):
                    ident = f'p{page["page"]:03d}-f{rank:02d}'
                    box = located['input_bbox']
                    pixels = [max(0, int(box[0]*page['width']/1000)-5), max(0, int(box[1]*page['height']/1000)-5),
                        min(page['width'], int(box[2]*page['width']/1000)+5), min(page['height'], int(box[3]*page['height']/1000)+5)]
                    destination = self.output / 'assets/figures' / f'{ident}.png'
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    image.crop(pixels).save(destination)
                    index = located['ref_index']
                    ref = page['references'][index-1] if index else {}
                    page_text = '\n\n'.join(page['descriptions'] + [f.get('text', '') for f in page['references']])
                    figures.append(dict(id=ident, page=page['page'], label=located['label'] or ref.get('label', ident),
                        ref_index=index, source_pointer=page['reference_pointers'][index-1] if index else None,
                        title=ref.get('title', ''), text=ref.get('text', ''), page_context=page_text,
                        context_source='complete existing book.json figure and page prose; no text truncation',
                        caption=located['caption'], grid_bbox=located['grid_bbox'], input_bbox=located['input_bbox'],
                        bbox=dict(zip(('x_min', 'y_min', 'x_max', 'y_max'), [x/1000 for x in located['grid_bbox']])),
                        bbox_pixels=pixels, crop=str(destination.relative_to(self.output)), crop_sha256=digest(destination),
                        input_image=page['input_image'], full_page_sha256=page['page_sha256'], detection_notes=located['notes']))
                    page['figure_ids'].append(ident)
        data['figures'] = figures
        write(self.output / 'manifest.json', data)
        print(f'crop: {len(figures)} independent diagrams with captions/full-page context', flush=True)

    def recognize(self):
        self.freeze()
        figures = read(self.output / 'manifest.json')['figures']
        groups = [figures[i:i+4] for i in range(0, len(figures), 4)]
        jobs = []
        for index, group in enumerate(groups):
            images, prompt = recognition_inputs(group, self.output)
            jobs.append(dict(stem=f'batch-{index:03d}', images=images, prompt=prompt, ids=[f['id'] for f in group]))
        print(f'board: {len(figures)} diagrams, {len(jobs)} batches, workers={self.workers}', flush=True)
        self.jobs('board', jobs, BOARD_SCHEMA, 'figures')

    def usage(self):
        counts = defaultdict(Counter)
        for path in (self.output / 'raw').glob('*/*/*/attempt-*.events.jsonl'):
            stage = path.relative_to(self.output / 'raw').parts[0]
            for line in path.read_text().splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get('type') == 'turn.completed' and isinstance(event.get('usage'), dict):
                    counts[stage]['logged_completed_requests'] += 1
                    counts[stage].update({k: v for k, v in event['usage'].items() if type(v) is int})
        for value in counts.values():
            value['total_tokens'] = value['input_tokens'] + value['output_tokens']
        return {stage: dict(value) for stage, value in counts.items()}

    def assemble(self):
        frozen = self.freeze()
        data = read(self.output / ('manifest.json' if (self.output / 'manifest.json').exists() else 'source.json'))
        old = self.old_results()
        boards, errors = {}, {}
        checkpoint = self.output / 'board-checkpoint.json'
        if checkpoint.exists():
            state = read(checkpoint)
            boards = {f['id']: (f, job) for job in state['jobs'] for f in job['response']['figures']}
            errors = {ident: f['error'] for f in state['failures'] for ident in f['ids']}
        for figure in data.get('figures', []):
            if figure['id'] in boards:
                board, job = boards[figure['id']]
                figure['result'] = convert_new(board)
                figure['recognition_provenance'] = dict(model=MODEL, reasoning=REASONING,
                    cache_key=job['cache_key'], batch=job['stem'], input_crop_sha256=figure['crop_sha256'],
                    full_page_sha256=figure['full_page_sha256'], coordinate_conversion='local_to_full_board_once')
            else:
                figure['result'] = dict(complete=False, error=errors.get(figure['id'], 'Recognition not run'), replay_status='pending')
            result = figure['result']
            figure['needs_review'] = (not result['complete'] or bool(result.get('uncertainties')) or
                bool(result.get('inferences')) or result.get('origin_uncertain', False))
        data['figures'] = merge_figures(old['figures'], data.get('figures', []))
        # Old full objects are immutable, including review evidence and full-board coordinates.
        if canonical_hash(data['figures'][:266]) != frozen['final_figures_sha256']:
            raise ValueError('old final266 changed during merge')
        for number, accepted in enumerate(old['pages']):
            data['pages'][number].update({key: deepcopy(value) for key, value in accepted.items()
                if key in ('figure_ids', 'detection_notes', 'detected_count', 'missing_reference_labels')})
            data['pages'][number]['detection_status'] = 'reused_final'
        coverage = coverage_report(data['pages'], data['figures'])
        page_outcomes = []
        by_page = defaultdict(list)
        for figure in data['figures']:
            by_page[figure['page']].append(figure)
        for page in data['pages']:
            failed = [dict(id=f['id'], error=f['result'].get('error')) for f in by_page[page['page']] if not f['result']['complete']]
            page_outcomes.append(dict(page=page['page'], status=page.get('detection_status', 'not_requested'),
                detected=len(by_page[page['page']]), zero_diagrams=page.get('detected_count') == 0,
                notes=page.get('detection_notes', ''), detection_error=page.get('detection_error'),
                recheck_error=page.get('detection_recheck_error'), recognition_errors=failed))
        data['summary'] = dict(pages=195, pages_detected=sum(p['status'] in ('complete', 'reused_final') for p in page_outcomes),
            figures=len(data['figures']), existing_refs=468, reused_final_figures=266,
            new_figures=len(data['figures'])-266, completed=sum(f['result']['complete'] for f in data['figures']),
            inferred_labels=sum(len(f['result'].get('inferences', [])) for f in data['figures']),
            uncertain_figures=sum(bool(f['result'].get('uncertainties')) for f in data['figures']),
            issues=sum(bool(f['result'].get('issues')) for f in data['figures']),
            review_figures=sum(f['needs_review'] for f in data['figures']), coverage_missing=len(coverage['missing']))
        data['coverage_missing'] = coverage['missing']
        write(self.output / 'results.json', data)
        write(self.output / 'coverage.json', dict(**coverage, page_outcomes=page_outcomes))
        mapping = {f['id']: dict(page=f['page'], ref_index=f['ref_index'],
            source_pointer=(data['pages'][f['page']-1]['reference_pointers'][f['ref_index']-1] if f['ref_index'] else None),
            figure_sha256=canonical_hash(f), reused_final=f['page'] <= 100) for f in data['figures']}
        write(self.output / 'recognition-index.json', dict(source_hashes=data['sources'], figures=mapping))
        write(self.output / 'audit.json', dict(frozen_first100=frozen, summary=data['summary'],
            old_usage_reference_only=read(self.old / 'audit.json')['usage_from_saved_codex_events'],
            new_usage_from_saved_events=self.usage(),
            usage_note='Old usage is reference only, not new consumption. Reasoning is included in output_tokens. Saved events are not subscription quota or billing.',
            accuracy_note='Visual model transcription; complete means response finished, never human verified. All replay remains pending without separate sequence evidence.',
            sources_unchanged=all(digest(path) == sha for path, sha in data['sources'].items())))
        # Existing viewer expects relative image URLs. Link old assets without changing old objects.
        for figure in old['figures']:
            for key in ('crop', 'review_crop'):
                if figure.get(key):
                    link = self.output / figure[key]
                    link.parent.mkdir(parents=True, exist_ok=True)
                    if not link.exists():
                        link.symlink_to(self.old / figure[key])
        for page in data['pages']:
            thumb = self.output / 'assets/pages' / f'page_{page["page"]:03d}.png'
            thumb.parent.mkdir(parents=True, exist_ok=True)
            if not thumb.exists():
                with Image.open(page['input_image']) as image:
                    image.thumbnail((210, 330))
                    image.convert('RGB').save(thumb)
            page['thumbnail'] = str(thumb.relative_to(self.output))
        embedded = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
        template = (self.old / 'viewer.html').read_text().replace('__BASE_CSS__', (self.old / 'base.css').read_text())
        (self.output / 'index.html').write_text(template.replace('__RESULTS_JSON__', embedded))
        print(json.dumps(data['summary'], ensure_ascii=False), flush=True)
        return data['summary']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'detect', 'crop', 'recognize', 'board', 'assemble', 'all'])
    parser.add_argument('--book-dir', type=Path, default=DEFAULT_BOOK)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--old-dir', type=Path, default=DEFAULT_OLD)
    parser.add_argument('--start-page', type=int, default=101)
    parser.add_argument('--end-page', type=int, default=195)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--attempts', type=int, default=2)
    args = parser.parse_args()
    runner = Runner(args.book_dir, args.output_dir, args.old_dir, args.start_page, args.end_page,
                    args.workers, args.timeout, args.attempts)
    if args.stage == 'all':
        runner.prepare()
        runner.detect()
        runner.crop()
        runner.recognize()
        summary = runner.assemble()
        return int(summary['pages_detected'] < 195 or summary['completed'] < summary['figures'])
    getattr(runner, 'recognize' if args.stage == 'board' else args.stage)()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
