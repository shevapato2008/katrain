# Static teaching annotations integration

User approved the actual source/component previews for book11 PDF10/11/13/14 and requested saving them to the TEST book. The cancelled media campaign remains cancelled.

## Plan

- [ ] Add optional, strictly bounded `board_payload.teaching_annotations`: schema_version1, registered source pointer/image SHA, fractional region dividers/arrows and Chinese margin callouts. Existing payloads remain unchanged.
- [ ] Use existing calibration CAS/history/media invalidation and verify source identity before saving. No schema migration or direct SQL updates.
- [ ] Integrate the three reviewed frontend commits into real Workbench read/edit/save; retain annotations when copying payloads. Reuse approved geometry. Frontend owner is the existing page10 agent.
- [ ] Focused model/API/source mismatch/history tests plus frontend read/save checks and build. No new model audit campaign.
- [ ] Update tutorial-gpt-recognition skill to preserve diagram-level teaching content separately from point marks, including source coordinates and provenance.
- [ ] Layer reviewed files/bundle on exact running TEST provider/console images, preserving configuration/services; verify service health and actual pages.
- [ ] Save only figures4275/4276/4278/4279 via authenticated calibration API, with current CAS and source pins, then record the user's explicit visual confirmation of these versions.
- [ ] Check persisted readback and actual board rendering; report the four links. Preserve old assets/history and never restart audio/video batches.
