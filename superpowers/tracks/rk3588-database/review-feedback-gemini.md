# Design Review Feedback: RK3588 Smart Board Database Architecture

> Reviewer: Gemini
> Date: 2026-02-09

## Summary Verdict

This is a strong, well-reasoned design document that correctly identifies the problems with alternative architectures. The choice of an "API-First with local SQLite fallback" pattern is the right approach for this problem, providing an excellent balance of security, scalability, and offline capability. The proposed implementation is detailed, pragmatic, and the phased roadmap significantly reduces risk. The design is mostly ready for implementation, but there are a few critical issues regarding data safety, security, and runtime state management that must be addressed before proceeding.

## Critical Issues (must fix before implementation)

1.  **Sync Failure Leads to Data Loss**: The current policy of "3 retries then give up" is dangerous. An entry that fails synchronization permanently is effectively lost data for the user. A dead-letter queue or a similar mechanism is needed. Failed items should be marked clearly as `failed` (not just left with `synced_at = NULL`) and there must be a way to inspect and manually retry these failed jobs, along with an alert mechanism for the server admin.

2.  **Physical Device Security is Insufficient**: The design does not account for the physical device being stolen. Storing a plaintext JWT and an unencrypted SQLite database containing user data on the device is a significant security risk.
    *   **Recommendation**: The JWT should be stored in an encrypted file or system keychain, not in process memory or a plaintext file. The local SQLite database itself should be encrypted at rest using a library like `SQLCipher`.

3.  **Ambiguous Repository Switching Logic**: The design is contradictory about how repositories are switched. It suggests injecting a repository at startup based on `KATRAIN_MODE` (Section 4.9), but also implies a runtime switch based on connectivity (Section 4.6). A startup-based switch cannot handle intermittent connectivity.
    *   **Recommendation**: Implement a "Dispatcher" pattern. At startup, instantiate a single `RepositoryDispatcher` which holds both the `LocalRepository` and `RemoteRepository` instances. For each method call, the dispatcher checks the current `ConnectivityManager.is_online` status and routes the call to the appropriate implementation. This provides clear, per-request, state-aware logic.

4.  **Undefined Guest-to-User Data Binding Flow**: The document states "联网后可选择绑定到远程账户" (can choose to bind to a remote account after connecting), but this critical and complex user workflow is not designed. How are local guest games and progress re-associated with a real user account? This involves UI prompts, user decisions, and modification of the `sync_queue` payloads before sending. This flow must be designed in detail.

## Recommendations (should consider)

1.  **Prevent Concurrent Sync Operations**: The `ConnectivityManager` could trigger a new sync while a previous one is still running, leading to race conditions or duplicate operations. Implement a concurrency lock (e.g., an `is_syncing` flag) to ensure only one sync process runs at a time.

2.  **Add Device Monitoring**: There is no way to know if a board has gone permanently offline and has unsynced data. The server should have a `devices` table or add a `last_seen` timestamp to the `users` table. A background job on the server should monitor this and raise an alert for devices that have not connected for an extended period (e.g., 7 days).

3.  **Automate Database Migration/Update**: The manual `rm db.sqlite3` step during an update is error-prone. This should be an automated script that: 1) Checks for network connectivity, 2) Triggers a final sync and waits for completion, 3) Deletes the old database file, 4) Starts the new application version, which will create a fresh DB.

4.  **Clarify Conflict Resolution Strategy**: The document claims "no conflict risk" which is not entirely accurate. It employs a conflict *avoidance* and *resolution* strategy (UUIDs, and "take max value" for tsumego attempts). The documentation should be rephrased to reflect this, acknowledging that it's a "last write wins" policy on certain fields, which is a deliberate design choice, not a complete absence of potential conflict.

## Minor Suggestions (nice to have)

1.  **Define Offline UI/UX**: Briefly describe what the user sees when they try to access an online-only feature (like the Kifu library) while offline. It should be a graceful degradation (e.g., a "not available offline" message) rather than a crash or blank page.

2.  **Persist JWT on Device**: To improve user experience, the JWT should be persisted across application restarts on the board. As mentioned in Critical Issues, this must be done securely.

3.  **Local Database Pruning**: To prevent unbounded growth of the local SQLite file, consider a simple cleanup policy, such as automatically deleting `user_games` records that were successfully synced more than 30 days ago.

## Questions for the Author

1.  **Multi-User Support?** Is the RK3588 board intended to be a single-user device, or can multiple users log in? The current design appears to assume a single-user context. If it's multi-user, the local cache and sync queue need to be designed to handle data from multiple users without mixing them.

2.  **Desired Tsumego Conflict Logic?** For `user_tsumego_progress`, is "take the max value of attempts" the correct business logic? Or should attempts made on different devices be cumulative (i.e., summed)?

3.  **Sync Failure Recovery?** What is the desired user/admin experience when a sync operation definitively fails after all retries? Does the user need to be notified? Should there be a UI for admins to inspect and re-trigger failed jobs?