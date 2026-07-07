#!/bin/sh
# MinIO bucket bootstrap (run once by the `minio-setup` compose service).
#
# Creates the tutorial-assets bucket and grants ANONYMOUS READ (D7: public-read
# bucket; abuse is fenced off at the nginx reverse proxy via Referer/domain
# allow-list, D6). Idempotent — safe to re-run.
set -eu

ALIAS=local
ENDPOINT="${MINIO_ENDPOINT:-http://minio:9000}"
BUCKET="${S3_BUCKET:-tutorial-assets}"

echo "[bootstrap] registering mc alias -> ${ENDPOINT}"
mc alias set "${ALIAS}" "${ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"

echo "[bootstrap] ensuring bucket '${BUCKET}'"
mc mb --ignore-existing "${ALIAS}/${BUCKET}"

echo "[bootstrap] setting anonymous download (public read) on '${BUCKET}'"
mc anonymous set download "${ALIAS}/${BUCKET}"

echo "[bootstrap] done. Current policy:"
mc anonymous get "${ALIAS}/${BUCKET}"
