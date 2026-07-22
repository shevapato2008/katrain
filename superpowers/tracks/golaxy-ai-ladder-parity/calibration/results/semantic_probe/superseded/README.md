# Superseded semantic-probe artifacts

These files are retained for audit history but are **not valid evidence for the
final HumanSL semantic-probe contract**. Do not cite them as passing results.

- `humansl_semantic_probe_20260721T181903Z.json`
- `humansl_semantic_probe_20260721T181949Z.json`
- `humansl_semantic_probe_20260721T182216Z.json`

  Schema 1 ran duplicated controls for each lambda (eight analysis requests),
  did not persist exact posted request bodies/IDs, and cannot be revalidated by
  the final validator.

- `humansl_semantic_probe_20260721T182855.288608Z_f883b41f79cc.json`

  Schema 2 used the unstable low lambda `1e-6`; a consecutive run exposed a
  zero-PSV secondary-order tie. It also lacks explicit execution order.

- `humansl_semantic_probe_20260721T183027.385201Z_284f091fff45.json`
- `humansl_semantic_probe_20260721T183027.845233Z_b0a9176c346d.json`
- `humansl_semantic_probe_20260721T183230.249150Z_90a6a6e7519f.json`

  Schema 2 used the stable locked lambda pair and exact five requests, but did
  not persist `case_order`. Because JSON `sort_keys` reorders request mappings,
  these files cannot round-trip through the final schema 3 validator.

Final citeable artifacts live one directory above, use `probe_schema: 3`, carry
an exact five-entry `case_order`, and must pass `validate_probe_results` after a
fresh `json.load`.
