#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DEPLOY_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

PHASE=capacity
FIXTURE=
ENV_FILE=
FAILURES=0
PEAK_BYTES=13500000000

usage() {
    printf 'usage: %s [--phase capacity|runtime|full] [--env-file FILE] [--fixture FILE] [--structural]\n' "$0"
}

fail() {
    printf 'ERROR %s\n' "$*" >&2
    FAILURES=$((FAILURES + 1))
}

while (($#)); do
    case $1 in
        --phase)
            (($# >= 2)) || die "--phase requires a value"
            PHASE=$2
            shift 2
            ;;
        --env-file)
            (($# >= 2)) || die "--env-file requires a value"
            ENV_FILE=$2
            shift 2
            ;;
        --fixture)
            (($# >= 2)) || die "--fixture requires a value"
            FIXTURE=$2
            shift 2
            ;;
        --structural)
            PHASE=structural
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage >&2
            die "unknown argument: $1"
            ;;
    esac
done

case $PHASE in
    capacity|runtime|full|structural) ;;
    *) die "invalid phase: $PHASE" ;;
esac

read_fixture() {
    local line key value
    [[ -f $FIXTURE ]] || die "fixture is not a regular file"
    while IFS= read -r line || [[ -n $line ]]; do
        [[ -z $line ]] && continue
        [[ $line == *=* ]] || die "invalid fixture entry"
        key=${line%%=*}
        value=${line#*=}
        [[ $value =~ ^[0-9]+$ ]] || die "fixture values must be numeric"
        case $key in
            AVAILABLE_BYTES|PEAK_BYTES|FS_TOTAL_BYTES|FS_USED_BYTES|INODE_TOTAL|INODE_USED|DOCKER_OK|COMPOSE_OK|GPU_OK|IMAGES_OK|SECRET_FILE_OK|PREVIEW_PROFILE_OK|PRODUCTION_PROFILE_OK|WG_PEER_OK|WG_ADDRESS_OK|FIREWALL_OK|PORTS_OK)
                printf -v "$key" '%s' "$value"
                ;;
            *) die "fixture key is not allowed: $key" ;;
        esac
    done < "$FIXTURE"
}

collect_capacity() {
    local disk_line inode_line docker_version compose_version
    require_command df
    require_command docker
    disk_line=$(df -B1 -P "$DEPLOY_DIR" | awk 'NR == 2 {print $2, $3, $4}')
    read -r FS_TOTAL_BYTES FS_USED_BYTES AVAILABLE_BYTES <<< "$disk_line"
    inode_line=$(df -Pi "$DEPLOY_DIR" | awk 'NR == 2 {print $2, $3}')
    read -r INODE_TOTAL INODE_USED <<< "$inode_line"
    if docker info >/dev/null 2>&1; then DOCKER_OK=1; else DOCKER_OK=0; fi
    docker system df >/dev/null 2>&1 || DOCKER_OK=0
    docker_version=$(docker version --format '{{.Server.Version}}' 2>/dev/null || true)
    compose_version=$(docker compose version --short 2>/dev/null || true)
    info "runtime docker_version=${docker_version:-unavailable} compose_version=${compose_version:-unavailable}"
}

check_capacity() {
    local required_bytes projected_used
    required_bytes=$((PEAK_BYTES + 25000000000))
    info "capacity available_bytes=$AVAILABLE_BYTES peak_bytes=$PEAK_BYTES required_bytes=$required_bytes"
    if ((AVAILABLE_BYTES < required_bytes)); then
        fail "migration requires at least $required_bytes bytes available"
    fi
    projected_used=$((FS_USED_BYTES + PEAK_BYTES))
    if ((projected_used * 100 >= FS_TOTAL_BYTES * 75)); then
        fail "projected filesystem use reaches or exceeds 75 percent"
    fi
    if (((INODE_TOTAL - INODE_USED) * 100 < INODE_TOTAL * 25)); then
        fail "projected free inodes fall below 25 percent"
    fi
    ((DOCKER_OK == 1)) || fail "Docker is unavailable"
}

fixture_flag() {
    local name=$1
    [[ ${!name:-0} == 1 ]] || fail "$name check failed"
}

render_structural() {
    local fake_web fake_cron fake_katago
    fake_web="sha256:$(printf '1%.0s' {1..64})"
    fake_cron="sha256:$(printf '2%.0s' {1..64})"
    fake_katago="sha256:$(printf '3%.0s' {1..64})"
    env POSTGRES_PASSWORD=test-only MINIO_ROOT_USER=test-only MINIO_ROOT_PASSWORD=test-only \
        KATRAIN_SECRET_KEY=test-only KATRAIN_DB_NAME=katrain_db KATRAIN_DB_USER=katrain_user \
        S3_BUCKET=tutorial-assets WEB_IMAGE="$fake_web" CRON_IMAGE="$fake_cron" \
        KATAGO_IMAGE="$fake_katago" WG_BIND_IP=10.8.0.3 \
        MEDIA_PUBLIC_BASE_URL=https://example.invalid/tutorial-assets ALERT_EMAIL=nobody@example.invalid \
        docker compose -f "$DEPLOY_DIR/compose.yml" config >/dev/null 2>&1 && \
    env POSTGRES_PASSWORD=test-only MINIO_ROOT_USER=test-only MINIO_ROOT_PASSWORD=test-only \
        KATRAIN_SECRET_KEY=test-only KATRAIN_DB_NAME=katrain_db KATRAIN_DB_USER=katrain_user \
        S3_BUCKET=tutorial-assets WEB_IMAGE="$fake_web" CRON_IMAGE="$fake_cron" \
        KATAGO_IMAGE="$fake_katago" WG_BIND_IP=10.8.0.3 \
        MEDIA_PUBLIC_BASE_URL=https://example.invalid/tutorial-assets ALERT_EMAIL=nobody@example.invalid \
        docker compose -f "$DEPLOY_DIR/compose.yml" -f "$DEPLOY_DIR/compose.production.yml" \
        --profile production config >/dev/null 2>&1
}

env_value() {
    local name=$1
    awk -v key="$name" 'index($0, key "=") == 1 {print substr($0, length(key) + 2); exit}' "$ENV_FILE"
}

check_runtime() {
    local mode image preview_services production_services preview_config production_config
    [[ -f $ENV_FILE ]] || { fail "runtime phase requires --env-file FILE"; return; }
    mode=$(stat -c '%a' "$ENV_FILE" 2>/dev/null || stat -f '%Lp' "$ENV_FILE" 2>/dev/null || true)
    [[ $mode == 600 ]] || fail "environment file mode must be 0600"

    for image_name in WEB_IMAGE CRON_IMAGE KATAGO_IMAGE; do
        image=$(env_value "$image_name")
        if [[ ! $image =~ ^sha256:[0-9a-f]{64}$ && ! $image =~ ^[^[:space:]]+@sha256:[0-9a-f]{64}$ ]]; then
            fail "$image_name is not immutable"
        elif ! docker image inspect "$image" >/dev/null 2>&1; then
            fail "$image_name is not available locally"
        fi
    done
    command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1 || fail "NVIDIA GPU is unavailable"

    if preview_services=$(docker compose --env-file "$ENV_FILE" -f "$DEPLOY_DIR/compose.yml" config --services 2>/dev/null) && \
       preview_config=$(docker compose --env-file "$ENV_FILE" -f "$DEPLOY_DIR/compose.yml" config 2>/dev/null); then
        [[ $(grep -c '^katrain-cron$' <<< "$preview_services") == 0 ]] || fail "preview profile includes katrain-cron"
        grep -Eq "KATRAIN_PREVIEW_MODE: ['\"]?1" <<< "$preview_config" || fail "preview profile mode is not 1"
    else
        fail "preview profile does not render"
    fi
    if production_services=$(docker compose --env-file "$ENV_FILE" -f "$DEPLOY_DIR/compose.yml" -f "$DEPLOY_DIR/compose.production.yml" --profile production config --services 2>/dev/null) && \
       production_config=$(docker compose --env-file "$ENV_FILE" -f "$DEPLOY_DIR/compose.yml" -f "$DEPLOY_DIR/compose.production.yml" --profile production config 2>/dev/null); then
        [[ $(grep -c '^katrain-cron$' <<< "$production_services") == 1 ]] || fail "production profile must include exactly one katrain-cron"
        grep -Eq "KATRAIN_PREVIEW_MODE: ['\"]?0" <<< "$production_config" || fail "production profile mode is not 0"
    else
        fail "production profile does not render"
    fi
}

check_full_network() {
    command -v wg >/dev/null 2>&1 && wg show 2>/dev/null | grep -q '^peer:' || fail "WireGuard peer is unavailable"
    command -v ip >/dev/null 2>&1 && ip -4 address show wg0 2>/dev/null | grep -q '10\.8\.0\.3' || fail "WireGuard address 10.8.0.3 is unavailable"
    if command -v iptables >/dev/null 2>&1; then
        iptables -S >/dev/null 2>&1 || fail "firewall rules are unreadable"
    elif ! command -v ufw >/dev/null 2>&1; then
        fail "firewall tooling is unavailable"
    fi
    command -v ss >/dev/null 2>&1 || fail "socket ownership tooling is unavailable"
}

if [[ -n $FIXTURE ]]; then
    read_fixture
else
    collect_capacity
fi
check_capacity

case $PHASE in
    capacity) ;;
    structural)
        if [[ -n $FIXTURE ]]; then
            fixture_flag COMPOSE_OK
        else
            if render_structural; then info "Compose preview and production profiles render"; else fail "Compose structure does not render"; fi
            if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=name --format=csv,noheader >/dev/null 2>&1; then
                info "NVIDIA GPU is available"
            else
                fail "NVIDIA GPU is unavailable"
            fi
        fi
        ;;
    runtime|full)
        if [[ -n $FIXTURE ]]; then
            fixture_flag SECRET_FILE_OK
            fixture_flag IMAGES_OK
            fixture_flag GPU_OK
            fixture_flag PREVIEW_PROFILE_OK
            fixture_flag PRODUCTION_PROFILE_OK
        else
            check_runtime
        fi
        if [[ $PHASE == full ]]; then
            if [[ -n $FIXTURE ]]; then
                fixture_flag WG_PEER_OK
                fixture_flag WG_ADDRESS_OK
                fixture_flag FIREWALL_OK
                fixture_flag PORTS_OK
            else
                check_full_network
            fi
        fi
        ;;
esac

if ((FAILURES > 0)); then
    info "preflight failed checks=$FAILURES"
    exit 1
fi
info "preflight passed phase=$PHASE"
