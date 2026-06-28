---
name: server-deploy
description: >
  Rebuild and restart the production Docker services (KataGo GPU engines, KaTrain web/cron,
  and the MinIO object-storage stack for tutorial media). Use when deploying code changes to
  the server, restarting services after updates, bringing up/​migrating tutorial media storage,
  or troubleshooting containers. Triggers on: deploy, 部署, restart services, rebuild docker,
  重启服务, 重新部署, server update, 更新服务器, minio, 对象存储, 媒体存储, storage backend.
---

# Server Deploy

Rebuild and restart the production Docker services for KaTrain, KataGo, and tutorial media storage.

## Service Architecture

```
                 ┌──────────────┐
  :8001          │  katrain-web │──▶ :8000 katago-gpu0 (GPU 0) ← user gameplay
                 └──────┬───────┘──▶ minio:9000 (tutorial media, S3 API)
                 ┌──────┴───────┐
                 │ katrain-cron │──▶ :8002 katago-gpu1 (GPU 1) ← batch analysis
                 └──────────────┘
                 ┌──────────────────┐        ┌─────────────────────────────────┐
  :5432          │ katrain-postgres │        │ katrain-minio  127.0.0.1:9000/9001│ ← tutorial media bytes
                 │  ← never restart │        │ katrain-minio-setup (one-shot)    │   (volume: minio-data)
                 └──────────────────┘        └─────────────────────────────────┘
```

| Container | Image | Port | GPU | Managed by | Source / Notes |
|-----------|-------|------|-----|------------|----------------|
| katago-gpu0 | katago-trt:latest | 8000 | 0 | `docker run` | /home/fan/Repositories/KataGo (develop) |
| katago-gpu1 | katago-trt:latest | 8002 | 1 | `docker run` | /home/fan/Repositories/KataGo (develop) |
| katrain-web | docker compose build | 8001 | — | **compose** | /home/fan/Repositories/katrain (develop); `depends_on: minio healthy` |
| katrain-cron | docker compose build | — | — | **compose** | /home/fan/Repositories/katrain (develop) |
| katrain-minio | minio/minio | 127.0.0.1:9000/9001 | — | **compose** | tutorial media object store (S3 API); volume `minio-data` |
| katrain-minio-setup | minio/mc | — | — | **compose** | one-shot: create bucket + anonymous read, then exits 0 |
| katrain-postgres | postgres | 5432 | — | external | **DO NOT restart** (shows as compose "orphan" — ignore) |

> The `katrain` compose project manages **web + cron + minio + minio-setup**. KataGo runs via
> raw `docker run` (separate repo, GPU pinning). Postgres is external. So `docker compose ...`
> in /home/fan/Repositories/katrain only ever touches web/cron/minio — never the GPU engines or DB.

## Tutorial media storage (MinIO) — read before deploying

Tutorial video/audio/page-image **bytes** live in object storage (MinIO now ≡ Aliyun OSS later),
**never in Postgres** (the DB only stores the relative path as the object key in
`tutorial_figures.video_asset` / `audio_asset`). The app reaches storage through a
`StorageBackend` abstraction chosen by `KATRAIN_STORAGE_BACKEND`:

- **`local`** → FastAPI streams bytes from `data/tutorial_assets/` with HTTP Range (current default behavior).
- **`s3`** → the `/assets` endpoint **302-redirects** clients to `KATRAIN_S3_PUBLIC_BASE_URL/{key}`
  (offloads bandwidth to MinIO/CDN). Requires that public URL to be **reachable from the client browser**.

### `.env` keys (in /home/fan/Repositories/katrain/.env)

```bash
DASHSCOPE_API_KEY=<key>                 # cron translation (existing)
POSTGRES_PASSWORD=<current db password> # pin to the running value; postgres only honors it at first init
# --- tutorial media storage ---
KATRAIN_STORAGE_BACKEND=local           # local (stream via app) | s3 (302 to public MinIO/CDN)
MINIO_ROOT_USER=katrain_minio_admin
MINIO_ROOT_PASSWORD=<strong secret>     # generate: openssl rand -hex 24
S3_BUCKET=tutorial-assets
# MEDIA_PUBLIC_BASE_URL=https://media.<domain>/tutorial-assets   # set only when MinIO is publicly exposed (Stage B)
```

> ⚠️ **The compose default for `KATRAIN_STORAGE_BACKEND` is `s3`.** If you bring services up
> without `KATRAIN_STORAGE_BACKEND=local` in `.env` **and** without a browser-reachable
> `MEDIA_PUBLIC_BASE_URL`, the app will 302 clients to an unreachable URL and **tutorial
> playback breaks**. Keep `local` until MinIO is exposed through the jump host (see Stage B).

### Deployment stages

- **Stage A (current)** — app on `local` backend; MinIO runs internally + holds a migrated copy
  of all assets. Zero user-facing change, no jump-host change. De-risks the cloud move.
- **Stage B (before launch)** — expose MinIO publicly (jump-host reverse tunnel `:9000` + nginx
  route for `media.<domain>` or a `/media/` path), set `MEDIA_PUBLIC_BASE_URL`, flip
  `KATRAIN_STORAGE_BACKEND=s3`. Then bytes are served directly by MinIO/CDN, not the app.
- **Phase 2 (Aliyun OSS)** — same S3 API; change only `.env` (`KATRAIN_S3_ENDPOINT_URL`,
  `KATRAIN_S3_REGION`, OSS keys, `MEDIA_PUBLIC_BASE_URL=https://cdn.<domain>`). No code change.

## Execution Steps

### 1. Ensure .env exists & is complete

```bash
cat /home/fan/Repositories/katrain/.env   # must have DASHSCOPE_API_KEY, POSTGRES_PASSWORD, and storage keys above
```

If a key is missing, copy it from the running container before recreating (recreate re-substitutes `.env`):

```bash
docker inspect katrain-web --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E 'DASHSCOPE|DATABASE_URL'
```

### 2. Rebuild KataGo image (~2-20 min) — only if /home/fan/Repositories/KataGo changed

```bash
cd /home/fan/Repositories/KataGo
docker build -t katago-trt:latest -f Dockerfile .
```

### 3. Restart KataGo containers — only if KataGo changed

```bash
docker stop katago-gpu0 katago-gpu1 && docker rm katago-gpu0 katago-gpu1
docker run -d --name katago-gpu0 --gpus '"device=0"' --restart unless-stopped -p 8000:8000 katago-trt:latest
docker run -d --name katago-gpu1 --gpus '"device=1"' --restart unless-stopped -p 8002:8000 katago-trt:latest
```

### 4. Verify KataGo health (TensorRT warmup ~30s-2min)

```bash
curl http://localhost:8000/health && curl http://localhost:8002/health
# expect: {"status":"ok",...,"has_human_model":true,...}
```

### 5. Object storage: bring up MinIO + bootstrap bucket (idempotent)

```bash
cd /home/fan/Repositories/katrain
docker compose up -d minio minio-setup
docker logs katrain-minio-setup            # expect: bucket created + anonymous policy = download
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9000/minio/health/live   # 200
```

`minio-setup` exits 0 after creating `tutorial-assets` with anonymous read (public-read bucket,
D7). Safe to re-run. The `minio-data` named volume persists the bytes across recreates.

### 6. Migrate / sync assets into MinIO (one-time, or after new assets generated)

Non-destructive (D8: local stays the authoritative mirror) and idempotent (size-matched objects
skipped). Run with `KATRAIN_STORAGE_BACKEND=s3` overridden (so it targets MinIO even while the
app stays on `local`), and suppress boto3 DEBUG noise:

```bash
cd /home/fan/Repositories/katrain
docker compose run --rm -T -e KATRAIN_STORAGE_BACKEND=s3 katrain-web python3 - <<'PY'
import logging; logging.basicConfig(level=logging.WARNING)
for n in ('botocore','boto3','urllib3','s3transfer'): logging.getLogger(n).setLevel(logging.WARNING)
import runpy; runpy.run_path('scripts/migrate_assets_to_minio.py', run_name='__main__')
PY
# ends with: "✓ all <N> local files present in bucket."  (count parity check)
```

(Equivalent: `mc mirror ./data/tutorial_assets local/tutorial-assets/tutorial_assets`.)

### 7. Rebuild & restart KaTrain web/cron

```bash
cd /home/fan/Repositories/katrain
docker compose up -d --build katrain-web katrain-cron
```

`--build` rebuilds Dockerfile.web (includes `npm run build`, ~60s) and Dockerfile.cron.
`katrain-web` waits for `minio` healthy (so step 5 must have run). Bare `docker compose up -d --build`
also (re)creates minio/minio-setup — fine, but never recreates KataGo/postgres.

### 8. Verify all services

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
curl http://localhost:8001/api/v1/health
docker exec katrain-web sh -c 'echo BACKEND=$KATRAIN_STORAGE_BACKEND'   # confirm intended backend (local/s3)
docker logs katrain-cron --tail 20
```

For `local` backend, also confirm an asset still streams (Range):

```bash
curl -s -o /dev/null -w 'asset %{http_code}\n' -H 'Range: bytes=0-1023' \
  "http://localhost:8001/api/v1/tutorials/assets/<some/known/key>.mp4"   # expect 206
```

## Selective Deployment

- **KataGo changes only**: steps 2-4
- **KaTrain code/frontend changes only**: steps 1, 7-8
- **Cron-only changes**: `docker compose up -d --build katrain-cron`
- **First MinIO bring-up**: step 5, then step 6 (full migration), then recreate web/cron (step 7)
- **New tutorial assets generated** (write-through already uploads on `s3`; on `local` MinIO isn't touched): re-run step 6 to sync
- **Flip to s3 (Stage B)**: set `MEDIA_PUBLIC_BASE_URL` + `KATRAIN_STORAGE_BACKEND=s3` in `.env`, then step 7

## Troubleshooting

- **Tutorial videos 404 / won't play after flipping to s3**: `KATRAIN_S3_PUBLIC_BASE_URL` not
  reachable from the browser. Either MinIO isn't exposed (jump-host route missing) or the URL is
  the `http://localhost:9000/...` placeholder. Revert `KATRAIN_STORAGE_BACKEND=local` to restore
  app-streamed playback while you fix the route.
- **`docker compose up` recreates web but it can't start**: `depends_on: minio healthy` — ensure
  `docker compose up -d minio minio-setup` ran and `katrain-minio` is healthy.
- **minio-setup exits non-zero**: check `MINIO_ROOT_USER/PASSWORD` in `.env`; inspect
  `docker logs katrain-minio-setup`.
- **migration "objects missing" / count mismatch**: re-run step 6 (idempotent; uploads only the gaps).
- **boto3 DEBUG flooding the migration log**: use the stdin wrapper in step 6 (pins botocore/boto3
  loggers to WARNING).
- **katrain-web can't reach KataGo**: containers use `host.docker.internal`. Check `docker logs katrain-web`.
- **"orphan containers (katrain-postgres)" warning**: normal — postgres isn't in compose. Ignore.
- **KataGo OOM on startup**: stale TensorRT plan cache → `docker exec katago-gpu0 rm -rf /tmp/*.engine`.
