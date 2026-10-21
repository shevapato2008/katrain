# Static teaching annotations integration

User approved the actual source/component previews for book11 PDF10/11/13/14 and requested saving them to the TEST book. The cancelled media campaign remains cancelled.

## Plan

- [x] Add optional, strictly bounded `board_payload.teaching_annotations`: schema_version1, registered source pointer/image SHA, fractional region dividers/arrows and Chinese margin callouts. Existing payloads remain unchanged.
- [x] Use existing calibration CAS/history/media invalidation and verify source identity before saving. No schema migration or direct SQL updates.
- [x] Integrate the three reviewed frontend commits into real Workbench read/edit/save; retain annotations when copying payloads. Reuse approved geometry. Frontend owner is the existing page10 agent.
- [x] Focused model/API/source mismatch/history tests plus frontend read/save checks and build. No new model audit campaign.
- [x] Update tutorial-gpt-recognition skill to preserve diagram-level teaching content separately from point marks, including source coordinates and provenance.
- [x] Layer reviewed files/bundle on exact running TEST provider/console images, preserving configuration/services; verify service health and actual pages.
- [x] Save only figures4275/4276/4278/4279 via authenticated calibration API, with current CAS and source pins, then record the user's explicit visual confirmation of these versions.
- [x] Check persisted readback and actual board rendering; report the four links. Preserve old assets/history and never restart audio/video batches.

## Completion evidence

- TEST backend `d5e107034755`, console UI `34fa5c69633c`; both containers healthy. Exact environment, ports, mounts and networks preserved. Three provider files and 85 UI assets matched deployment manifests.
- Figures 4275/4276/4278/4279 saved through authenticated calibration CAS API, then confirmed using the user’s explicit visual approval. Full before/after and operation receipts are in `output/tutorial-static-integration-20261021/`.
- Real TEST admin pages checked at 1920×1080: PDF10 two vertical/two horizontal dividers, PDF11 16 callouts, PDF13 four arrows, PDF14 two arrows plus the two original white stones. Screenshots are in `output/playwright/tutorial-static-test-20261021/`.
- Focused checks: 76 backend tests, 121 frontend tests, frontend typecheck/build, Pydantic 2.6 provider smoke and actual persisted readback passed.
- Narration/audio unchanged. Old video links invalidated for the corrected board versions by the existing calibration behavior; old files/history retained. No media jobs resumed or generated. PDF12 left unchanged.
