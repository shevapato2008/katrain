# V100 Preview Gateway Routing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the existing UCloud V100 KaTrain Web service at `https://v100-preview.sailorvoyage.top` through the Alibaba Cloud WireGuard gateway while leaving `go.sailorvoyage.top` on home-ubuntu.

**Architecture:** Add one DNS A record and one isolated Nginx virtual host on the Alibaba gateway. The virtual host terminates its own TLS certificate, proxies application and WebSocket traffic to `10.8.0.3:8001`, proxies `/media/` to V100 MinIO at `10.8.0.3:9000/tutorial-assets/`, and rejects registration POSTs. Update only the V100 Web container's media public base URL and preserve its database, state volume, platform adapters, and no-cron boundary.

**Tech Stack:** AliDNS, Nginx, Certbot/Let's Encrypt, WireGuard, Docker Compose, FastAPI/React KaTrain Web, MinIO, curl/OpenSSL

**Specification:** `docs/superpowers/specs/2026-07-30-v100-preview-gateway-routing-design.md`

---

## Chunk 1: Safe infrastructure rollout

### Task 1: Record the baseline and rollback inputs

**Files:**
- Inspect: `/etc/nginx/sites-available/go.sailorvoyage.top` on `alicloud-ecs-gateway`
- Inspect: `/etc/katrain/ucloud.env` on `ucloud-v100`
- Inspect: `/opt/katrain/current/deploy/ucloud/compose.yml` on `ucloud-v100`
- Inspect: `/opt/katrain/current/deploy/ucloud/compose.production.yml` on `ucloud-v100`

- [ ] **Step 1: Confirm both existing routes and services before mutation**

Run from the local workstation:

```bash
ssh alicloud-ecs-gateway 'curl -fsS http://10.8.0.2:8001/api/v1/health && curl -fsS http://10.8.0.3:8001/api/v1/health && curl -fsS http://10.8.0.3:9000/minio/health/live'
```

Expected: both KaTrain health requests return JSON and MinIO returns HTTP 200.

- [ ] **Step 2: Capture the non-secret gateway and V100 runtime baseline**

Run:

```bash
ssh alicloud-ecs-gateway 'sudo readlink -f /etc/nginx/sites-enabled/go.sailorvoyage.top; sudo grep -nE "server_name|proxy_pass" /etc/nginx/sites-available/go.sailorvoyage.top; sudo certbot certificates'
ssh ucloud-v100 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"; docker inspect katrain-ucloud-katrain-web-1 --format "image={{.Image}} project={{index .Config.Labels \"com.docker.compose.project\"}}"; docker exec katrain-ucloud-katrain-web-1 python -c "from katrain.web.core.config import settings; print(\"mode=\" + settings.KATRAIN_MODE)"; docker inspect katrain-ucloud-katrain-web-1 --format "{{range .Config.Env}}{{println .}}{{end}}" | grep -E "^(KATRAIN_REMOTE_URL|KATRAIN_S3_PUBLIC_BASE_URL)=" || true; docker ps -a --format "{{.Names}}" | grep -E "(^|-)katrain-cron-" || true'
```

Do not print passwords, database URLs, tokens, or platform credential contents.

Expected: `go.sailorvoyage.top` targets `10.8.0.2:8001`; V100 Web binds only `127.0.0.1:8001` and `10.8.0.3:8001`; MinIO binds only loopback/WireGuard; `KATRAIN_REMOTE_URL` is absent; no V100 cron is running.

- [ ] **Step 3: Confirm a controlled tester can authenticate before public activation**

Open a temporary local tunnel through the gateway without exposing V100 publicly:

```bash
ssh -N -L 18001:10.8.0.3:8001 alicloud-ecs-gateway
```

In a browser, open `http://127.0.0.1:18001/galaxy/` and have every nominated tester authenticate in turn using their existing V100 KaTrain account. Log out between testers. Credentials stay in the browser; record only success/failure, then close the tunnel.

Expected: every nominated tester authenticates against the V100 database; otherwise stop before DNS/Nginx mutation.

- [ ] **Step 4: Save exact rollback copies before editing**

Run and retain the printed backup path:

```bash
ssh alicloud-ecs-gateway 'stamp=$(date +%Y%m%d%H%M%S); if sudo test -e /etc/nginx/sites-available/v100-preview.sailorvoyage.top; then sudo cp -a /etc/nginx/sites-available/v100-preview.sailorvoyage.top /etc/nginx/sites-available/v100-preview.sailorvoyage.top.pre-rollout-$stamp; fi'
ssh ucloud-v100 'stamp=$(date +%Y%m%d%H%M%S); backup=/etc/katrain/ucloud.env.pre-v100-preview-$stamp; sudo cp -a /etc/katrain/ucloud.env "$backup"; sudo chmod 600 "$backup"; sudo stat -c "%a %U:%G %n" "$backup"; docker inspect katrain-ucloud-katrain-web-1 --format "{{.Image}}"'
```

Expected: backups exist with root-only permissions; no service has restarted.

### Task 2: Create the preview DNS record

**Files:**
- Modify externally: AliDNS zone `sailorvoyage.top`

- [ ] **Step 1: Detect the available authenticated DNS management path**

Check for an authenticated Aliyun CLI/profile without printing credentials. If available, query only the `v100-preview` record. Otherwise use the authenticated Alibaba Cloud console session.

Expected: the record is absent or its record ID, value, and TTL are recorded for exact rollback.

- [ ] **Step 2: Add or minimally update the A record**

Set:

```text
RR: v100-preview
Type: A
Value: 8.130.171.106
```

Do not modify `go`, `api-go`, the zone's name servers, or unrelated records.

- [ ] **Step 3: Verify authoritative and public resolution**

Run:

```bash
dig +short v100-preview.sailorvoyage.top @dns31.hichina.com
dig +short v100-preview.sailorvoyage.top @223.5.5.5
```

Expected: `8.130.171.106` from both after propagation.

### Task 3: Install the complete isolated virtual host and obtain TLS

**Files:**
- Create: `/etc/nginx/sites-available/v100-preview.sailorvoyage.top` on `alicloud-ecs-gateway`
- Create: `/etc/nginx/sites-enabled/v100-preview.sailorvoyage.top` symlink on `alicloud-ecs-gateway`
- Create via Certbot: `/etc/letsencrypt/live/v100-preview.sailorvoyage.top/*` on `alicloud-ecs-gateway`

- [ ] **Step 1: Write the complete HTTP bootstrap virtual host**

Install this full policy before the hostname is enabled, so registration is blocked from the first public request:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name v100-preview.sailorvoyage.top;
    include /etc/nginx/snippets/letsencrypt.conf;
    include /etc/nginx/snippets/acme_logging.conf;

    location = /api/v1/auth/register {
        if ($request_method = POST) { return 403; }
        proxy_pass http://10.8.0.3:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /media/ {
        proxy_pass http://10.8.0.3:9000/tutorial-assets/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_buffering off;
        valid_referers none blocked server_names *.sailorvoyage.top sailorvoyage.top;
        if ($invalid_referer) { return 403; }
    }

    location / {
        proxy_pass http://10.8.0.3:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        send_timeout 60s;
    }
}
```

- [ ] **Step 2: Validate before activation**

Run:

```bash
sudo nginx -t
```

Expected: syntax and configuration tests are successful. If not, restore/remove only the preview site and do not reload.

- [ ] **Step 3: Enable and reload the fully protected HTTP site**

Create the site-enabled symlink and reload Nginx only after another successful `nginx -t`.

- [ ] **Step 4: Obtain a separate certificate**

Run non-interactive Certbot for only the preview name:

```bash
sudo certbot --nginx --non-interactive --agree-tos --redirect -d v100-preview.sailorvoyage.top
```

Use the gateway's already configured Certbot account email. Do not expand the existing `go.sailorvoyage.top` certificate.

Expected: a distinct certificate lineage exists for `v100-preview.sailorvoyage.top`; `nginx -t` passes.

### Task 4: Verify Certbot preserved the preview-only proxy policy

**Files:**
- Modify: `/etc/nginx/sites-available/v100-preview.sailorvoyage.top` on `alicloud-ecs-gateway`

- [ ] **Step 1: Inspect the Certbot result**

Confirm the HTTPS server still contains the exact registration location, V100 MinIO location, and general V100 app/WebSocket location shown in Task 3. Confirm Certbot added only preview certificate paths and an HTTP-to-HTTPS redirect.

- [ ] **Step 2: Validate and reload atomically**

Run `sudo nginx -t`, reload Nginx, then run `sudo nginx -t` once more. If validation fails, disable only `/etc/nginx/sites-enabled/v100-preview.sailorvoyage.top`, validate, and reload; leave `go` untouched.

Expected: Nginx is active, and the `go` configuration file and certificate lineage are unchanged.

### Task 5: Point V100 media redirects to the preview hostname

**Files:**
- Modify: `/etc/katrain/ucloud.env` on `ucloud-v100`
- Use: `/opt/katrain/current/deploy/ucloud/compose.yml` on `ucloud-v100`
- Use: `/opt/katrain/current/deploy/ucloud/compose.production.yml` on `ucloud-v100`

- [ ] **Step 1: Update only the public media base URL**

Set the environment variable consumed by Compose (`MEDIA_PUBLIC_BASE_URL`, yielding Web `KATRAIN_S3_PUBLIC_BASE_URL`) to:

```text
https://v100-preview.sailorvoyage.top/media
```

Apply one asserted replacement:

```bash
ssh ucloud-v100 'set -eu; test "$(sudo grep -c "^MEDIA_PUBLIC_BASE_URL=" /etc/katrain/ucloud.env)" = 1; sudo sed -i "s#^MEDIA_PUBLIC_BASE_URL=.*#MEDIA_PUBLIC_BASE_URL=https://v100-preview.sailorvoyage.top/media#" /etc/katrain/ucloud.env; sudo chmod 600 /etc/katrain/ucloud.env; sudo grep "^MEDIA_PUBLIC_BASE_URL=" /etc/katrain/ucloud.env; sudo stat -c "%a %U:%G %n" /etc/katrain/ucloud.env'
```

Expected: exactly that public value is printed and permissions remain `600 root:root`; every other line is preserved. Leave `KATRAIN_REMOTE_URL` unset.

- [ ] **Step 2: Recreate only Web from the already deployed image/config**

Run:

```bash
ssh ucloud-v100 'cd /opt/katrain/current && sudo docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml up -d --no-deps --force-recreate katrain-web'
```

The base file declares project `katrain-ucloud`; the production override sets `KATRAIN_PREVIEW_MODE=0` and the production state volume. Do not use `--profile production` or `--build`, and do not target cron, MinIO, PostgreSQL, or KataGo.

Expected: only the Web container is recreated; its image ID is unchanged; database and state volumes remain attached; no cron container starts.

- [ ] **Step 3: Verify runtime boundaries immediately**

Run the Task 1 baseline commands again plus:

```bash
ssh ucloud-v100 'docker inspect katrain-ucloud-katrain-web-1 --format "{{range .Config.Env}}{{println .}}{{end}}" | grep -E "^(KATRAIN_PREVIEW_MODE|KATRAIN_REMOTE_URL|KATRAIN_S3_PUBLIC_BASE_URL)=" || true; curl -fsS http://10.8.0.3:8001/api/v1/health'
```

Expected: Web is healthy; `KATRAIN_MODE` is server; `KATRAIN_REMOTE_URL` is absent; public media base is the preview URL; `engines.local == "reachable"`; no V100 cron runs.

## Chunk 2: Public verification and acceptance

### Task 6: Verify routing, security boundary, media, and production isolation

**Files:**
- No repository or server file changes

- [ ] **Step 1: Verify DNS and TLS from outside the gateway**

Run:

```bash
dig +short v100-preview.sailorvoyage.top @223.5.5.5
curl --noproxy '*' -fsS https://v100-preview.sailorvoyage.top/api/v1/health
openssl s_client -connect v100-preview.sailorvoyage.top:443 -servername v100-preview.sailorvoyage.top -verify_return_error -verify_hostname v100-preview.sailorvoyage.top </dev/null
```

Expected: DNS is `8.130.171.106`; OpenSSL reports `Verify return code: 0 (ok)`; health is HTTP 200 and reports `engines.local` as `reachable`.

- [ ] **Step 2: Verify the Galaxy UI and authenticated lobby WebSocket in the browser**

Open `/galaxy/` in a browser, authenticate as the nominated tester, enter the human-vs-human lobby, and inspect the browser Network panel entry for `/ws/lobby?token=...`. Record only that the handshake status is `101` and that the first non-sensitive frame type is `lobby_update`; never copy the URL token, cookies, or payload contents into the rollout record.

Expected: `/galaxy/` renders successfully, the WebSocket handshake is `101 Switching Protocols`, and the first frame type is `lobby_update`.

- [ ] **Step 3: Verify registration is rejected but ordinary auth remains routed**

Run with unique nonexistent names:

```bash
curl --noproxy '*' -sS -o /tmp/v100-preview-register.out -w '%{http_code}\n' -H 'Content-Type: application/json' -d '{"username":"preview_registration_must_fail_20260730","email":"preview-registration-must-fail-20260730@example.invalid","password":"not-a-real-secret"}' https://v100-preview.sailorvoyage.top/api/v1/auth/register
curl --noproxy '*' -sS -o /tmp/v100-preview-login.out -w '%{http_code}\n' -H 'Content-Type: application/json' -d '{"username":"preview_nonexistent_login_20260730","password":"not-a-real-secret"}' https://v100-preview.sailorvoyage.top/api/v1/auth/login
```

Expected: registration is gateway HTTP 403; login reaches the application and returns its normal invalid-credentials HTTP 401, not gateway 403. Remove the two temporary response files after recording only their status codes.

- [ ] **Step 4: Verify a real media object is served by V100 MinIO**

Obtain one key without printing database credentials:

```bash
ssh ucloud-v100 'docker exec katrain-ucloud-postgres-1 sh -c '\''psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT COALESCE(video_asset,audio_asset) FROM tutorial_figures WHERE video_asset IS NOT NULL OR audio_asset IS NOT NULL LIMIT 1"'\'''
```

For the returned `<key>`, inspect the application redirect and compare the same first 1024 bytes through public Nginx and direct V100 MinIO from the gateway:

```bash
curl --noproxy '*' -sS -o /dev/null -D - "https://v100-preview.sailorvoyage.top/api/v1/tutorials/assets/<key>"
curl --noproxy '*' -fsS -H 'Range: bytes=0-1023' "https://v100-preview.sailorvoyage.top/media/<key>" -o /tmp/v100-preview-public.range
ssh alicloud-ecs-gateway 'curl -fsS -H "Range: bytes=0-1023" "http://10.8.0.3:9000/tutorial-assets/<key>"' > /tmp/v100-preview-direct.range
shasum -a 256 /tmp/v100-preview-public.range /tmp/v100-preview-direct.range
```

Expected: the application redirect `Location` starts with `https://v100-preview.sailorvoyage.top/media/`; public media returns 200/206; both range files have identical SHA-256 values. Remove both temporary files afterward.

- [ ] **Step 5: Prove `go.sailorvoyage.top` still targets home-ubuntu**

Compare the live `go` Nginx upstream and a request routed with `Host: go.sailorvoyage.top` to the direct home service at `10.8.0.2:8001`. Also confirm the preview site's upstream is `10.8.0.3:8001`.

Expected: `go` remains home; preview remains V100.

### Task 7: Perform controlled real-platform acceptance

**Files:**
- No server file changes; credentials are entered only by the tester in the browser

- [ ] **Step 1: Authenticate an existing V100 KaTrain user**

Open `https://v100-preview.sailorvoyage.top/galaxy/` and sign in with an account already present in the V100 database. Do not send credentials through shell history, logs, screenshots, or chat.

Expected: login succeeds; a new registration remains impossible through the preview hostname.

- [ ] **Step 2: Test a real Golaxy account connection**

The tester enters their own Golaxy credentials in the UI, connects, confirms live lobby/account state, and uses the platform disconnect/logout action when finished. Do not delete their saved credentials unless they explicitly request it.

Expected: real Golaxy connectivity succeeds through the preview deployment. Only one tester uses the Golaxy adapter at a time.

- [ ] **Step 3: Test a real OGS account connection**

The tester enters their own OGS credentials in the UI, connects, confirms live lobby/account state, and uses the platform disconnect/logout action when finished. Do not delete their saved credentials unless they explicitly request it.

Expected: real OGS connectivity succeeds through the preview deployment. Only one tester uses the OGS adapter at a time.

- [ ] **Step 4: Record the Fox capability gap honestly**

While authenticated, inspect the browser Network response for `/api/v1/platforms/status` and record only that Fox reports `supports_live_play: false`. Confirm the corresponding UI does not present Fox as live-play ready. Record that Fox real login/live play was not accepted because its upstream endpoints/protocol are unavailable in the current implementation.

### Task 8: Finalize or roll back

**Files:**
- Modify: `docs/superpowers/plans/2026-07-30-v100-preview-gateway-routing.md`

- [ ] **Step 1: Run the final compact verification set**

Repeat health/engine status, Galaxy, WebSocket, media Range, registration rejection, no-cron, server-mode, remote-URL-unset, port-binding, and unchanged-`go` checks using fresh outputs.

- [ ] **Step 2: Mark completed checkboxes and record acceptance evidence**

Record only statuses, timestamps, non-sensitive response summaries, and any manual tester confirmation. Never commit credentials, cookies, tokens, or secret environment values.

- [ ] **Step 3: Roll back only if a release-blocking check fails**

Perform rollback in this order:

1. On V100, read only the prior `MEDIA_PUBLIC_BASE_URL` line from the saved environment backup, assert that the current file contains exactly one such line, replace only that current line, restore `600 root:root`, and rerun the exact Web-only Compose command from Task 5.
2. Verify V100 Web health, engine reachability, image ID, production state volume, bindings, no cron, and unchanged `KATRAIN_REMOTE_URL`.
3. On the gateway, unlink only `/etc/nginx/sites-enabled/v100-preview.sailorvoyage.top`, run `sudo nginx -t`, reload Nginx, and run `sudo nginx -t` again. Keep the available-site file and certificate as rollback evidence until diagnosis completes.
4. Verify `go.sailorvoyage.top` still reaches `10.8.0.2:8001`.
5. Remove or restore the preview DNS record using the saved record ID/value/TTL only if the preview hostname must be withdrawn.

Do not replace the whole V100 environment file and do not touch `go`, its certificate, home-ubuntu, databases, state volumes, MinIO data, or KataGo.

- [ ] **Step 4: Commit the completed rollout record**

```bash
git add docs/superpowers/plans/2026-07-30-v100-preview-gateway-routing.md
git commit -m "docs: record V100 preview rollout"
```

Expected: the commit contains only the rollout plan/evidence; `katrain/web/static/pinyin-compose.js` remains untracked and untouched.
