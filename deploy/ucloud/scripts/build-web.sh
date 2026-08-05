#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/../../.." && pwd)
source "$SCRIPT_DIR/lib.sh"

IMAGE_TAG=${1:-}
[[ -n $IMAGE_TAG ]] || die "usage: build-web.sh <immutable-candidate-tag>"
[[ $IMAGE_TAG == *:* && $IMAGE_TAG != *:latest ]] || die "candidate image tag must be explicit and must not use latest"
[[ $IMAGE_TAG != *[[:space:]]* ]] || die "candidate image tag must not contain whitespace"
require_command docker

docker build --file "$ROOT_DIR/Dockerfile.web" --tag "$IMAGE_TAG" "$ROOT_DIR"

IMAGE_SIZE=$(docker image inspect --format '{{.Size}}' "$IMAGE_TAG")
[[ $IMAGE_SIZE =~ ^[0-9]+$ ]] || die "Docker returned a non-numeric image size"
(( IMAGE_SIZE <= 5000000000 )) || die "candidate image exceeds the 5000000000-byte limit"

docker run --rm "$IMAGE_TAG" sh -ec '
python -c '\''import httpx, cv2, numpy, fastapi, sqlalchemy, boto3; import katrain.web.server'\''
find /app/katrain/i18n/locales -name '\''katrain.mo'\'' -type f | grep -q .
test "HOME=$HOME" = HOME=/home/katrain
touch "$HOME/.write-test" && rm "$HOME/.write-test"
python -c '\''from katrain.web.platforms.credentials import PlatformCredentialStore; PlatformCredentialStore(secret="container-content-test")'\''
test ! -d /app/katrain/web/ui
test ! -d /app/tests
! command -v node
! command -v nvcc
'

IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE_TAG")
printf 'image_id=%s\nsize_bytes=%s\n' "$IMAGE_ID" "$IMAGE_SIZE"
