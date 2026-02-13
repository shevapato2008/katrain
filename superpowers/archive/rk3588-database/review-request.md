# Design Review Request: RK3588 Smart Board Database Architecture

> Reviewer: Gemini / Codex
> Document under review: `design.md` (same directory)
> Date: 2026-02-09

## Project Context

KaTrain is a Go/Baduk/Weiqi AI teaching application. It has a web version (FastAPI + React) with a PostgreSQL database on a cloud server. We're now deploying it to multiple RK3588 ARM development boards ("smart Go boards") that need to:

1. Access cloud data when online (tsumego problems, game records, user accounts)
2. Still function when offline (play against local KataGo AI, save games locally)
3. Sync offline data back to the cloud when reconnected

The design document proposes an **API-First + local SQLite offline cache** architecture.

---

## What to Review

Please read `design.md` and provide feedback on the following areas. Be specific — point out concrete issues, missing edge cases, or better alternatives. If something is well-designed, say so briefly and move on.

### 1. Architecture Decision

- Is **API-First + local SQLite fallback** the right choice for this use case (multiple ARM boards, intermittent connectivity, shared cloud database)?
- Are there alternative patterns we should consider that weren't evaluated? (e.g., CouchDB/PouchDB sync, service workers, etc.)
- Is the decision to **not** cache tsumego/kifu data locally for offline use the right tradeoff, or will users expect offline access to these features?

### 2. Sync Queue Design (Section 4.5)

- Is the `sync_queue` table schema sufficient? Are there missing fields?
- Is the "3 retries then give up" policy reasonable? What happens to failed entries — are they stuck forever?
- The document claims "no conflict risk" due to UUID keys and append-only semantics. **Challenge this claim** — are there any edge cases where conflicts could occur? (e.g., same user logging in on two boards, tsumego progress divergence)
- Is there a risk of **duplicate syncs** if the connectivity manager triggers sync while a previous sync is still running?

### 3. Connectivity Detection (Section 4.6)

- Is 10-second polling interval appropriate? Too frequent? Too slow?
- The "3 consecutive failures → offline, 2 consecutive successes → online" hysteresis — is this the right threshold?
- What happens during the **transition period** (e.g., a request comes in while state is switching from online to offline)? Is there a race condition?
- Should the board also consider **latency** (not just reachability) when deciding online/offline?

### 4. Authentication Flow (Section 5)

- The board acts as an API proxy — it receives the user's JWT from the remote server and caches it locally. **Security concern**: is storing the JWT in FastAPI process memory sufficient? What about restart persistence?
- What happens when the JWT expires while the user is **in the middle of playing offline**? When they reconnect, can the sync still authenticate?
- The "guest mode" for offline usage — how does the guest user ID map to a real user when they go back online? Is there a merge/binding flow?

### 5. Repository Abstraction (Section 4.8)

- Is Python `Protocol` the right pattern here, or would a simpler approach (e.g., just an `if/else` in each endpoint based on mode) be more pragmatic?
- The document suggests "gradual migration" — is there a risk of the codebase ending up in a half-migrated state permanently?
- Should the repository switch happen **per-request** (based on current connectivity) or **at startup** (based on KATRAIN_MODE)?

### 6. Missing Concerns

Please identify anything important that's **not addressed** in the document:

- **Error handling**: What does the user see when the board is offline and they try to access tsumego/kifu? A blank page? An error message? A graceful fallback UI?
- **Data volume**: Over time, how much data accumulates in the local SQLite? Is there a cleanup strategy?
- **Monitoring/observability**: How do we know if a board's sync is failing silently?
- **Security**: The board stores JWT tokens, has a local SQLite with user data — what's the threat model for a physical device that could be stolen?
- **Firmware/OTA updates**: How does the board get code updates? The document mentions `rm db.sqlite3` as part of the update flow — should this be automated?
- **Multi-user on one board**: Can multiple users log in to the same physical board? If so, how does the local SQLite handle multiple user contexts?

### 7. Implementation Roadmap (Section 8)

- Is the phasing order correct? Would you reorder any phases?
- Are there any phases that could be parallelized?
- Is the estimated complexity reasonable for each phase?

---

## Response Format

Please structure your response as:

```
## Summary Verdict
[One paragraph: overall assessment of the design]

## Critical Issues (must fix before implementation)
1. ...
2. ...

## Recommendations (should consider)
1. ...
2. ...

## Minor Suggestions (nice to have)
1. ...
2. ...

## Questions for the Author
1. ...
```
