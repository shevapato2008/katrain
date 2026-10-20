# OGS LearningHub source export

`export_course.mjs` converts the registered OGS course into the frozen schema v1
JSON contract. It reads local files only, runs no downloaded JavaScript, calls no
models, and performs no database, storage, or server operations.

Required inputs:

- A clean checkout at OGS commit `1c1c2b82d027f7c307ab25886112cf0a6baf680a`,
  including `src/views/LearningHub/` and `LICENSE`. The exporter checks HEAD and
  rejects modifications to those tracked files.
- The private research directory containing `other-language-catalogs.json` and
  `browser-sample-capture.json`, frozen to locale revision
  `5304fd731af8856a16d198d506111d61`. The former contains 28 locale scripts; the
  latter contains Japanese/Traditional Chinese scripts and the already extracted
  Simplified Chinese catalog. English comes from original source messages.
- Node.js and the TypeScript compiler module from the existing frontend
  development dependencies. No OGS app dependencies or Goban checkout are needed
  to export. If module resolution cannot find TypeScript, set
  `OGS_TYPESCRIPT_MODULE` to the installed `typescript` directory.

```sh
OGS_TYPESCRIPT_MODULE=/absolute/path/to/node_modules/typescript \
node scripts/ogs/export_course.mjs \
  --source-root /absolute/path/to/ogs-upstream \
  --catalog-root /absolute/path/to/private-research \
  --output /absolute/path/to/private-output/course.json
```

`--research-root` is an alias for `--catalog-root`. `coverage.json` is written
beside the bundle unless `--coverage PATH` is supplied. Keep the generated course,
catalogs and captures outside Git. The exporter does not populate screenshots.

The AST reader follows the actual `sections` registration and each lesson's
`pages()` return value. It supports literal configurations, gettext/pgettext,
static JSX paragraphs and radio option labels, authored correct/wrong paths, and
the three known ending-game handlers. Catalog scripts are parsed as AST object
literals; neither locale scripts nor React lesson modules are executed.

The expected course has seven chapters, 248 lessons and 3,551 steps: 3,028 puzzle
trees, 520 radio questions, one Pass, one dead-stone selection and one Finish.
Unknown recognized-page structures remain as `exercise.kind="unsupported"` with
an explicit issue; integrity failures, including opposite-color setup overlap,
reject the export. Same-color duplicates are deduplicated in normalized stones,
retained in `raw_source.config`, and reported. Missing locale keys retain their
English value and set that step's `translations[locale].fallback=true`; this flag
means at least one field used fallback. An unchanged English catalog value is
preserved and is not classified as a missing translation. Coverage `missing` and
`unchanged` count text-field uses, while `message_keys` counts unique source keys.

## Contract and provenance

- Chapters use `id="ogs-learning:<source group>"`; lessons use their original
  route; steps use `source_id="ogs-learning:<original route>:<one-based step>"`.
  `page` is the one-based ordinal through the entire book and `first_page` is the
  lesson's first global page. Original routes, including `bl;3-skills-5`, are kept
  unchanged in IDs. Source URL route segments are URI encoded and source step URL
  indexes are zero based, including explicit `/0` for the first step.
- `size`, `initial_player`, `stones`, `letters`, `shapes` and `viewport` match the
  frozen frontend/API contract. Coordinates use the original top-left origin;
  cropping affects display only. Omitted dimensions default to nine and omitted
  initial player to black. Marks retain letter/number strings or
  `cross`/`triangle`/`square` shape values.
- `exercise.tree` has `{point,correct,wrong,children}` at every node, with root
  `point=null`. A non-root null is a pass. Correct and wrong flags are independent
  and remain on all nodes. The exporter does not flatten, replay or repair paths.
- `exercise.choices` contains stable `value` plus original `label_key`;
  `correct_choice` is compared with the stable value. Localized labels are in
  `translations[locale].choices[value]`. Multi-paragraph instructions are joined
  with a blank line after independently translating each original message.
- `raw_source` retains file/class names, source file SHA, original config source,
  literal upstream config, authored path strings and their decode dimensions.
  `raw_source.config.move_tree` uses native Goban `{x,y,branches}` and
  `correct_answer`/`wrong_answer` flags, so a consumer can initialize the pinned
  engine without reverse engineering the normalized tree. Missing source defaults
  remain missing in raw config; consumers must apply defaults. Known ending-game
  conditions and button implementations are retained as evidence.
- Chapter and lesson translations include title; lessons also include subtext.
  Step translations include title, instruction, radio labels and fallback status.
  `source.ui_translations[locale]` supplies the six original feedback/action
  strings (`correct`, `incorrect`, `next`, `retry`, `pass`, `finish`). These plus
  lesson and chapter text cover all 883 source message keys in 32 languages.
- `source` records original repository, source/locale versions, pinned Goban
  revision `d7eb38eb4e9e1c48ace12befb98d9f3c821ec2f3`, license and complete license
  text. Lesson files are OGS AGPL-3.0-or-later material; this export makes no
  additional claims about rights to website assets or public commercial release.
- Source issues include the root wrong flag on `bl3-joseki-1` step four, six
  `bp-ko` setup deduplications, and suspicious Simplified Chinese instructions
  saying the opposite initial player. Source text is preserved without correction.

`source.content_sha256` hashes UTF-8 canonical JSON for the entire bundle, with
that hash field itself and each step's optional `screenshot` removed. Object keys
are sorted recursively; array order is preserved; whitespace is absent. This
matches Python `json.dumps(data, sort_keys=True, ensure_ascii=False,
separators=(',', ':'))`. No capture timestamps or machine-local paths enter the
export. The same inputs therefore produce byte-identical JSON and content hash;
later screenshot additions do not alter course identity.

## Focused checks

```sh
OGS_RESEARCH_ROOT=/absolute/path/to/private-research \
OGS_TYPESCRIPT_MODULE=/absolute/path/to/node_modules/typescript \
python -m pytest tests/web_ui/test_ogs_course_bundle.py -q
```

The Python consumer tests extract the actual full registered course when private
inputs are available, check complete counts and translations, the four frozen
examples, global ordering, multibranch depth, defaults, root anomaly, deduplication,
collision rejection, pass coordinates and Python/JavaScript hash agreement.
Without private research inputs, only the two full-course checks are skipped.
