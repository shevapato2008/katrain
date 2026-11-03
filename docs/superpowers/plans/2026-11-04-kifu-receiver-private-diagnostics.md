# Receiver Private Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking. The controller arranges independent Astra max review before any installation.

**Goal:** Capture the private cause of the next normal hourly receiver exit without replaying or changing its request, output channels, database behavior, or exit status.

**Architecture:** Preserve the exact existing forced wrapper as a fixed, root-owned executable backup. A temporary fixed Python launcher inherits stdin directly, runs only that backup, forwards stdout and stderr through independent pumps, and retains bounded copies in private files. Log initialization failure falls back to `exec` of the original wrapper; failures while writing a copy disable that copy while forwarding/draining continues.

**Tech Stack:** Python 3 standard library, the existing forced SSH command and Docker receiver, root-owned local files. No service, schema, application or scheduled-job changes.

---

## Chunk 1: Offline preparation and review

**Existing authority:** `/usr/local/sbin/kifu-incremental-receive-root`, exact SHA256 `6970924370b31ee4776473283e0608295060568cb3a0e0e602a677ac81953a0c`:

```sh
#!/bin/sh
set -eu
exec /usr/bin/docker exec -i katrain-ucloud-katrain-web-1 /bin/sh -c 'KIFU_INGEST_DATABASE_URL="$KATRAIN_DATABASE_URL" exec python3 /app/scripts/kifu_incremental.py receive'
```

The symbolic environment expression above is retained byte for byte. The launcher neither reads nor records environment values, stdin, SSH command text or arguments. It does not choose publication keys, invoke a receiver manually, add a timeout, or cancel a receiver.

**Files:**

- Create this plan: `docs/superpowers/plans/2026-11-04-kifu-receiver-private-diagnostics.md`.
- Prepare ignored launcher: `output/kifu-rank-hourly-20261103/receiver-private-diagnostics/launcher.py`.
- Prepare ignored fake-process tests: `output/kifu-rank-hourly-20261103/receiver-private-diagnostics/test_launcher.py`.
- Prepare fixed controller operator: `output/kifu-rank-hourly-20261103/receiver-private-diagnostics/operator.py` (`check`, `install`, `restore`); embedded launcher bytes must match the reviewed launcher SHA. Exact SSH invocations are in `operator-commands.txt`; temporary-directory safety tests are in `test_operator.py`.
- Record only offline test evidence and reviewed SHA files beside these scripts. No installation in this task.

### Task 1: Fixed launcher and focused tests

- [x] Write failing fake-process tests, then run them before writing the launcher:

```sh
/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m unittest discover -s output/kifu-rank-hourly-20261103/receiver-private-diagnostics -p test_launcher.py -v
```

Expected initial result: missing `launcher.py`. Expected final result: all focused cases pass.

- [x] Implement a launcher with these fixed production constants; no arguments or environment-based configuration are accepted:

```python
ORIGINAL = '/usr/local/sbin/kifu-incremental-receive-root.original-6970924370b3'
ORIGINAL_SHA256 = '6970924370b31ee4776473283e0608295060568cb3a0e0e602a677ac81953a0c'
LOG_ROOT = '/var/lib/kifu-incremental-receiver-private'
STDOUT_CAP = 16 * 1024 * 1024
STDERR_CAP = 1 * 1024 * 1024
```

- [x] Validate that the backup is a root-owned regular file, is not a symlink, has mode `0700`, and matches the original SHA. An invalid backup fails closed; it must never become an execution choice supplied by a request.
- [x] Require the log parent to be root-owned, mode `0700`, and a real directory. Create each run using `mkdtemp` (`0700`), and create stdout/stderr/metadata files exclusively with mode `0600`. Do not print log content into normal operator output.
- [x] Record UTC start/end, launcher/child PID, original exit status, copy byte counts, truncation and local write/channel failures. Do not independently read or add stdin, environment, SGF, extra request material or command arguments to the logs. Only the original output streams receive private copies; metadata is bounded and private.
- [x] Run the fixed backup with inherited stdin and environment, no command string, no extra arguments, and separate stdout/stderr pipes. Two non-daemon threads forward each channel's bytes in order and retain at most its cap; truncation affects only the saved copy.
- [x] Log setup failure silently `exec`s the fixed verified backup before starting a child, restoring Python's ignored pipe/file-size signals as normal subprocess execution does. Later log-copy failure must not change the child result. A closed outer output channel disables forwarding on that channel while continuing to drain its child pipe, so diagnostics cannot block the transaction on an unread pipe.
- [x] Forward only signals actually received (`HUP`, `INT`, `TERM`) to the one child; create no cancellation timer or process-group kill. Wait for and drain the child. Preserve ordinary exit codes, and reproduce signal termination after writing metadata. `SIGKILL`/machine loss cannot produce completion metadata and is not treated as a completed run.
- [x] Verify fake child exits `0`, `2`, `3`; binary stdin/individual output channels; copies exceeding both caps while original streams remain complete; setup failure fallback; mid-copy write failure; forbidden arguments; received signal forwarding; child SIGKILL status without traceback; closed channel without deadlock. Tests override constants only inside isolated fake harnesses, never via production CLI flags.
- [x] Run `py_compile` and record launcher/test SHA256. Send this plan and exact files to the controller for independent Astra max review. Only the plan may be committed; scripts remain ignored temporary operations artifacts.


**Offline preparation evidence (2026-11-04):** RED observed missing launcher and later the child SIGKILL defect; GREEN 9 fake-process launcher tests and 6 temporary-directory operator tests passed. `py_compile` passed. Launcher SHA256 `a9a397be8ecd4df7d89ea1c1ff18d766509a85d28b0e277869057a00e4de7b31`; operator SHA256 `6d8297f2505337ec76c97764957ad9d84d04df08c3daff625bfb37f792da82d3`. Both exact output channels and 0/2/3/negative-signal status are covered. Operator tests cover read-only checking, exact install/restore, immutable retained backup, active-receiver refusal before writes, foreign wrapper/backup refusal, and a change during final process inspection. Test transcript and hash manifest remain in the ignored output directory. Fresh read-only PROD metadata at 21:49:03Z confirms original root:root 0755 wrapper and expected SHA, secure /usr/local/sbin and /var/lib, no backup/private log directory, expected running container, and no receiver PIDs. No installation or remote file write was performed. Final independent code approval is pending.

## Chunk 2: Controller installation after approval (not authorized by this preparation task)

### Task 2: Install without invoking business work

- [ ] Obtain fresh read-only metadata on the real host: expected root account and container, the exact current wrapper SHA, owner, mode and regular-file/no-symlink status. Check `/usr/local/sbin` and the chosen log parent are root-owned and not writable by other users. Reject changed or foreign objects rather than repairing them automatically.
- [ ] Confirm there is no active forced wrapper/backup/diagnostic launcher or `kifu_incremental.py receive`, including the container's processes. Defer while any receiver is active; do not stop it. Recheck immediately before replacing/restoring the forced path, outside the next hourly launch window.
- [ ] Create the fixed backup exclusively, root-owned mode `0700`, from the verified original bytes. Verify its SHA. If a backup already exists, require the exact expected owner/type/mode/SHA and leave its bytes and metadata untouched. Keep this original for rollback; never overwrite it.
- [ ] Stage the reviewed launcher in the same root-owned directory using an exclusive regular file, root-owned mode `0700`. Verify its reviewed SHA and the backup again. Atomically replace only `/usr/local/sbin/kifu-incremental-receive-root` with that launcher. Keep the forced SSH/sudo policy, fixed Docker command, container and environment expression unchanged. No service restart or receiver invocation is needed.
- [ ] Wait for the existing scheduler's next natural retry. No manual publication, replay, new key, checkpoint reset, database write, gate change, or paid provider call is part of this diagnostic change. The naturally scheduled receiver retains its existing authority and normal business behavior.

### Task 3: Inspect one natural round, then restore

- [ ] Read only the resulting small metadata first. A started run without end metadata remains in progress/unknown; do not infer rollback or retry it manually. Correlate timestamps with the existing hourly stage and original key without printing request bodies.
- [ ] The controller inspects bounded private stderr/stdout locally on the host as needed. Do not copy raw logs into chat or general logs: they may contain private receipt or exception material. Share only a reviewed, redacted cause and small scalar evidence; never credentials, environment, SGF or stdin.
- [ ] After one completed natural round, confirm no receiver is active again. Verify the forced path is still exactly the reviewed launcher and the fixed backup still has its original SHA/ownership/type/mode. If another party changed either, stop rather than overwrite its work.
- [ ] Stage a copy of the unchanged original bytes beside the forced path, mode/owner matching the original wrapper metadata captured at installation, verify SHA, and atomically restore it. Verify forced path SHA is again `6970924370b31ee4776473283e0608295060568cb3a0e0e602a677ac81953a0c`. Keep the private evidence and immutable original backup; any later deletion is a separate explicit housekeeping action.

**Reviewed R1 adjustments:** Use `/var/lib/kifu-incremental-receiver-private` because fresh PROD metadata confirms `/var/lib` is root:root `0755`, with no symlink; leave group-writable `/var/log` untouched. SIGKILL propagation skips installing an unsupported signal handler and terminates the launcher with the same signal. The controller reviews the fixed install/restore operator alongside the revised launcher before any write.

**Completion evidence:** approved launcher SHA; fresh before/after wrapper metadata and SHA; one natural run's start/end/exit and bounded private files; exact restoration proof. This preparation task completes with offline tests and review submission only, without claiming installation or diagnosis of the production error.
