# PRD: Dual Engine Analysis (Local Subprocess + Cloud HTTP) for KaTrain

## Overview
Provide KaTrain with both local KataGo analysis for fast interactive feedback and cloud KataGo analysis for deeper review and teaching workflows, while keeping the UI consistent.

## Goals
- Preserve the existing local KataGoEngine experience.
- Add a cloud analysis option via KataGo request API (HTTP/WebSocket).
- Keep analysis display and game-play move generation consistent regardless of source.
- Allow manual or automatic engine selection by task type.

## Non-Goals
- Removing local KataGo support.
- Building a remote KataGo management UI.
- Changing KaTrain rules, SGF handling, or training logic.

## Personas
- Player: needs fast feedback while playing.
- Reviewer: needs strong analysis for post-game study.
- Teacher: needs consistent analysis during lessons.

## User Stories
- As a player, I want local analysis to stay responsive on my device.
- As a reviewer, I want to use cloud analysis for deeper insight.
- As a teacher, I want to switch engines without changing how I use KaTrain.
- As a cautious user, I want control over when positions are sent to the cloud.

## Functional Requirements
- Engine profiles: Local (subprocess) and Cloud (HTTP).
- Routing policy: manual selection and optional automatic routing (play vs review/teacher mode).
- Engine source labeling in the analysis UI.
- Unified analysis data model for both engine types.
- Game-play move generation can use either source.
- Fallback to local when cloud is unavailable.

## UX Requirements
- Toggle or selector for Local vs Cloud engine.
- Clear source indicator in analysis panels.
- Friendly error messages and retry paths for cloud outages.

## Performance and Reliability
- Local analysis remains low-latency for real-time play.
- Cloud analysis can be higher latency but deeper.
- Debounce navigation and cache per-node analysis.

## Privacy and Security
- Explicit opt-in for cloud analysis.
- Support TLS/auth for cloud endpoints.
- Minimize data sent beyond game position.

## Risks and Mitigations
- Complexity: standardize analysis normalization and reduce UI branching.
- Latency: show local results first, replace with cloud when ready.
- Cost control: allow user limits on cloud usage.

## Milestones (Suggested)
- Phase 1: Add engine profile UI and selection.
- Phase 2: Integrate HTTP analysis path and normalization.
- Phase 3: Add routing policy, caching, fallbacks, and usage limits.

## Open Questions
- What routing policy should decide Local vs Cloud automatically?
- How should the UI indicate Local vs Cloud across views?
