# Receiver private diagnostics — independent Astra review

Date: 2026-11-04. Latest result: **R2 APPROVED, final operator identity `6d8297f2505337ec76c97764957ad9d84d04df08c3daff625bfb37f792da82d3`**. Scope: the temporary privileged launcher, its offline fake-process tests, and the fixed controller operator added in R2; no installation, network access, receiver invocation, or business-data inspection. The original R1 findings are retained below, followed by their disposition.

## Plan review — approved

Reviewed `docs/superpowers/plans/2026-11-04-kifu-receiver-private-diagnostics.md` before inspecting the prepared implementation. The plan is sufficient for the narrowly scoped diagnostic change: exact fixed backup, private bounded output copies, inherited stdin/environment, unchanged business command, explicit pre-installation ownership/hash/activity checks, and restoration after one completed natural round. No blocking plan changes are required. This verdict is not installation approval.

## Specification compliance review — changes required

The fixed paths and SHA, rejection of arguments, backup validation, private modes, separate output forwarding, copy limits, silent initialization fallback, and ordinary exit-code behavior match the plan. The existing eight fake-process tests pass independently, and the three artifact hashes match the supplied manifest.

Signal-exit preservation is incomplete because of finding R1-1 below. In particular, a live launcher can observe its child being killed by `SIGKILL`; that differs from the launcher itself receiving `SIGKILL`, when completion metadata is inherently unavailable.

## Code quality review — changes required

### R1-1 — preserve child SIGKILL termination without adding a traceback

**Priority:** P1, required before installation.

**Location:** `output/kifu-rank-hourly-20261103/receiver-private-diagnostics/launcher.py:207–210`.

For every negative child status, the launcher first calls `signal.signal(signum, signal.SIG_DFL)`. `SIGKILL` cannot have a handler installed, including `SIG_DFL`; this raises `OSError(EINVAL)`. A child killed with signal 9 therefore becomes launcher exit 1, and Python adds its own traceback to the original stderr channel. This violates both original exit-status preservation and the requirement that diagnostics not add output to those channels.

**Independent reproduction:** using the existing isolated fake harness, run a child containing `os.kill(os.getpid(), signal.SIGKILL)`. Result: expected return code `-9`, actual return code `1`, private metadata child exit status `-9`, and added stderr from the invalid `signal.signal` call. Only synthetic process output was inspected.

**Required correction:** skip handler installation for `SIGKILL` and terminate the launcher with the same signal. Add a focused fake-process test asserting signal 9 return status and no added stdout/stderr. Preserve the existing catchable-signal behavior. Refresh the script/test hashes and the recorded test evidence, then request the focused second review.

No other blocking privilege or behavior issue was found in this scoped review. No extra infrastructure, production replay, or broad regression suite is required.

## Reviewed artifacts and validation

- Launcher SHA256: `9e78b4661c3627ddda36823097828c49c4aa053f8802f2bf234dbcfd6f17d363`.
- Test SHA256: `0ec0c552fdee194c3e7b0609f231ec87b748cff702a28e3a0e08e1e28abd32bd`.
- Supplied test transcript SHA256: `c5c613685402ee312287e452ef4686e952a36154c0e0396b24f8474c9dacbf6f`.
- Independent existing suite: eight tests passed in 2.296 seconds.
- Additional focused synthetic SIGKILL case: failed as described above.

The plan is approved; implementation approval is withheld until R1-1 is fixed and reviewed. No protected album directory was read, listed, or traversed, and no service or production state was changed.

## R2 specification compliance review — approved

R1-1 is resolved: the launcher skips handler installation for uncatchable signals and reproduces child `SIGKILL` termination without adding output. The new focused fake-process test asserts return code `-9`, empty stdout/stderr, and the recorded child status. The existing catchable-signal test still passes.

The fixed log location is now `/var/lib/kifu-incremental-receiver-private`. This conforms to the approved requirement for a private directory under a protected parent. The controller reports fresh root:root `0755` metadata for `/var/lib`; the operator independently enforces the parent ownership/type/mode before any mutation. `/var/log` is neither used nor changed. This is a concrete installation-location adjustment, not a new plan cycle.

The operator accepts only `check`, `install`, or `restore`. It embeds exactly the reviewed launcher bytes and expected SHA, retains the original fixed wrapper SHA, requires protected parents, validates existing objects without repairing foreign ones, uses exclusive staging and atomic replacement, rechecks receiver inactivity before replacement, and restores original bytes with the recorded `0755` mode. It leaves the original backup and private evidence in place. Its only subprocess call is the fixed read-only Docker container status inspection; it does not launch a receiver, modify a database, restart a service, or trigger a schedule.

## R2 code quality review — approved

No blocking privilege or behavior defects remain in the reviewed scope. Backup and target checks reject unexpected type, owner, mode, SHA, and target replacement during staging. The fixed original backup remains `0700`; installed diagnostics remain `0700`; the private directory remains `0700`. Host `/proc` inspection recognizes the fixed wrapper/backup, the Docker shell command, and the container Python receiver process without printing their arguments. The second inactivity check occurs immediately before the atomic replacement.

The operator's checks do not reserve the scheduler or lock out a future launch; the approved plan's requirement to perform replacement outside the hourly launch window still applies. Runtime guard failures must defer the operation without stopping a receiver or bypassing the guard. Restoration remains required after one completed natural diagnostic round. These are the existing operating constraints, not additional approval steps.

### R2 independent validation

- Fresh execution of the launcher suite: **9 tests passed in 2.323 seconds**.
- Operator embedded launcher bytes equal the reviewed `launcher.py` byte for byte, and the embedded SHA matches.
- Isolated temporary-directory `check → install → restore` passed: `check` made no backup/log directory, installation used the reviewed bytes and private modes, restoration recovered exact original bytes and `0755`, and the original backup remained unchanged.
- Synthetic activity appearing at the second inactivity check prevented replacement and preserved the original wrapper and backup.
- Four synthetic active command shapes were rejected: fixed launcher path, fixed backup path, Docker shell receiver command, and container Python receiver command. Docker inspection was mocked; no production process, container, or receiver was invoked.

### R2 approved artifact identities

- Launcher SHA256: `a9a397be8ecd4df7d89ea1c1ff18d766509a85d28b0e277869057a00e4de7b31`.
- Test SHA256: `9614faf152de504d06507fe3f6658ed2dd4b27fc8c95d5b727cd6fa52fadca11`.
- Initial R2 operator SHA256: `f62c61e49f3a502fa14db60a4329644b34898c26f3b9c71405d582f7ceb87254` — **superseded by the final identity below**.

The R1 hash manifest was stale when first read during R2; the controller was notified to refresh the evidence without changing these approved scripts. Approval is bound to the exact hashes above and the planned runtime guards. No installation or production diagnosis is claimed by this review.

## R2 final artifact identity confirmation — approved

The operator was subsequently changed during the R2 review to verify the backup and target immediately after the second process inspection and before `os.replace`. This prevents a foreign target change made during that inspection from being overwritten. It is a final validation before replacement, not a kernel-level compare-and-swap or a scheduler lock; the existing outside-launch-window constraint remains applicable.

I reviewed only this small change and the new operator tests. Replacing this changed block with the previously reviewed block reproduces SHA256 `f62c61e49f3a502fa14db60a4329644b34898c26f3b9c71405d582f7ceb87254` exactly, confirming no other operator changes. A fresh independent run of all six operator tests passed in 0.022 seconds, including the foreign target mutation during the final inactivity check. The launcher is unchanged, and the embedded launcher still matches its reviewed bytes and SHA.

**Final approved identities, superseding the earlier operator identity:**

- Operator SHA256: `6d8297f2505337ec76c97764957ad9d84d04df08c3daff625bfb37f792da82d3`.
- Operator-test SHA256: `8595907371d636af7bc0e0472f4d0c8711513f787e9e42d053553622d63e15da`.
- Launcher SHA256, unchanged: `a9a397be8ecd4df7d89ea1c1ff18d766509a85d28b0e277869057a00e4de7b31`.

Specification compliance and code quality remain approved for these exact artifacts under the existing plan and runtime guards. No installation was performed by the reviewer.
