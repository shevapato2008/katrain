# V100 Preview Gateway Routing Design

## Goal

Expose the KaTrain Web service running on UCloud V100 at
`https://v100-preview.sailorvoyage.top` without changing the existing
`go.sailorvoyage.top` production route to home-ubuntu.

The preview endpoint is for a small, controlled group of testers. Testers use
their normal KaTrain accounts and sign in to their own Golaxy, OGS, or Fox
accounts again on V100. Platform credentials are not copied from home-ubuntu.

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

The gateway terminates TLS. V100 ports 8001 and 9000 remain unavailable on its
public interface and are reachable only through loopback and WireGuard.

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

## V100 Runtime Boundaries

- Keep platform adapters enabled so real Golaxy, OGS, and Fox connections can
  be tested.
- Do not start `katrain-cron` on V100.
- Continue using the V100 database and V100 KaTrain state volume.
- Set the public S3/media base URL to
  `https://v100-preview.sailorvoyage.top/media` so preview media does not route
  through home-ubuntu.
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
test group; simultaneous users must not assume independent concurrent
connections to the same platform.

## Rollout and Verification

Before reloading Nginx, save a timestamped backup and require `nginx -t` to
pass. Verify from the gateway that `10.8.0.3:8001` and the V100 MinIO health
endpoint are reachable.

After activation, verify:

- public DNS resolves the preview hostname to `8.130.171.106`;
- HTTPS certificate validation succeeds;
- `/api/v1/health` and `/galaxy/` return success through the preview hostname;
- WebSocket upgrade works;
- media requests use the preview hostname and V100 MinIO;
- a tester can authenticate and connect to the required real platforms;
- `go.sailorvoyage.top` still proxies to `10.8.0.2:8001`.

Rollback disables only the new preview virtual host, restores the previous
V100 media public URL if it was changed, and reloads Nginx. Existing production
DNS and the `go.sailorvoyage.top` virtual host are never modified.
