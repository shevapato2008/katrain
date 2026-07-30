# V100 Preview Gateway Routing Design

## Goal

Expose the KaTrain Web service running on UCloud V100 at
`https://v100-preview.sailorvoyage.top` without changing the existing
`go.sailorvoyage.top` production route to home-ubuntu.

The preview endpoint is for a small, controlled group of testers. Testers use
existing KaTrain accounts and sign in to their own Golaxy or OGS accounts again
on V100. Platform credentials are not copied from home-ubuntu. Fox is visible
as an adapter but real Fox login and live play are outside this rollout because
the repository records its third-party endpoints as offline and its live-play
protocol as unimplemented.

## Current State

- Public DNS for `go.sailorvoyage.top` resolves to the Alibaba Cloud gateway.
- The gateway proxies `go.sailorvoyage.top` to home-ubuntu at
  `10.8.0.2:8001` over WireGuard.
- UCloud V100 is reachable from the gateway at `10.8.0.3`; its KaTrain health
  endpoint is available at `10.8.0.3:8001`.
- `v100-preview.sailorvoyage.top` has no DNS record, certificate, or Nginx
  virtual host.
- V100 runs production application behavior so real platform adapters are
  enabled, but no V100 cron scheduler is running.

## Architecture

```text
Browser
  -> HTTPS v100-preview.sailorvoyage.top:443
  -> Alibaba Cloud Nginx gateway (8.130.171.106)
  -> WireGuard 10.8.0.3:8001
  -> UCloud V100 katrain-web
```

The gateway terminates TLS. The deployed UCloud Compose stack binds Web to
`127.0.0.1:8001` and `10.8.0.3:8001`, and MinIO to `10.8.0.3:9000` (with its
console on loopback). V100 ports 8001 and 9000 remain unavailable on its public
interface and are reachable only through loopback and WireGuard.

The existing route remains unchanged:

```text
go.sailorvoyage.top -> 10.8.0.2:8001 (home-ubuntu)
```

## Gateway and DNS Changes

1. Add an A record for `v100-preview.sailorvoyage.top` pointing to the Alibaba
   Cloud gateway at `8.130.171.106`.
2. Create a separate Nginx virtual host for the preview hostname.
3. Proxy `/` to `http://10.8.0.3:8001` and preserve the original request URI,
   including `/galaxy/`.
4. Forward the standard proxy headers and WebSocket upgrade headers used by
   the existing KaTrain site.
5. Proxy `/media/` to the V100 MinIO service at
   `http://10.8.0.3:9000/tutorial-assets/`.
6. Issue a separate Let's Encrypt certificate for the preview hostname. Do not
   alter the certificate or virtual host for `go.sailorvoyage.top`.
7. Reject `POST /api/v1/auth/register` in the preview virtual host. Existing
   users can log in normally, but the public preview hostname cannot create new
   KaTrain accounts.

## V100 Runtime Boundaries

- Keep platform adapters enabled so real Golaxy and OGS connections can be
  tested. Fox live play remains a documented capability gap.
- Keep production application behavior and the V100 production state volume,
  but start only `katrain-web` with `--no-deps`; do not create or start the
  production-profile `katrain-cron` service.
- Continue using the V100 database and V100 KaTrain state volume.
- Set the public S3/media base URL to
  `https://v100-preview.sailorvoyage.top/media` so preview media does not route
  through home-ubuntu. Recreate only `katrain-web` after changing this value.
- Leave `KATRAIN_REMOTE_URL` unset on `katrain-web`; that variable is only for
  board-mode devices. A physical board should use the preview URL only when it
  is intentionally enrolled in V100 testing.
- Rely on normal KaTrain authentication. No gateway Basic Auth is added.

## Credentials and Concurrency

Platform credentials remain keyed by KaTrain `user_id` and platform. The
home-ubuntu credential database is not copied. Each tester signs in again on
V100.

The current platform manager has one live adapter per platform per server
process. The preview endpoint is therefore limited to a small, coordinated
test group. At most one tester may use a given platform at a time. Before a
different tester uses that platform, the current tester must explicitly log
out/disconnect. Golaxy and OGS may be used concurrently by different testers
because each has a separate adapter.

Only users already present in the V100 database may enter the preview. Before
rollout, confirm each nominated tester can authenticate against that database.
The V100 credential SQLite database and encryption salt remain in the V100
state volume; no home-ubuntu credential files are transferred.

## Rollout and Verification

Before reloading Nginx, save a timestamped backup and require `nginx -t` to
pass. Verify from the gateway that `10.8.0.3:8001` and the V100 MinIO health
endpoint are reachable. Verify on V100 that 8001 and 9000 bind only loopback or
`10.8.0.3`, never `0.0.0.0` or its public address.

After activation, verify:

- public DNS resolves the preview hostname to `8.130.171.106`;
- HTTPS certificate validation succeeds;
- `/api/v1/health` returns HTTP 200 with `engines.local == "reachable"`, and
  `/galaxy/` returns success through the preview hostname;
- WebSocket upgrade works;
- media requests use the preview hostname and V100 MinIO;
- preview registration is rejected while an existing tester can authenticate;
- real Golaxy and OGS login and connection work after the tester signs in
  again; Fox is reported as unavailable rather than claimed as live-play ready;
- only one tester at a time uses each real platform adapter;
- no `katrain-cron` container or process is running;
- `KATRAIN_MODE` resolves to server mode and `KATRAIN_REMOTE_URL` is unset;
- `go.sailorvoyage.top` still proxies to `10.8.0.2:8001`.

Rollback disables only the new preview virtual host, restores the previous
V100 media public URL if it was changed, recreates only `katrain-web`, and
reloads Nginx. Existing production DNS and the `go.sailorvoyage.top` virtual
host are never modified. The previous V100 image and environment-file backup
remain available until preview verification completes.
