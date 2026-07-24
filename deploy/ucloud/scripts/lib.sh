#!/usr/bin/env bash
set -Eeuo pipefail

timestamp() {
    date -u '+%Y-%m-%dT%H:%M:%SZ'
}

info() {
    printf '%s INFO %s\n' "$(timestamp)" "$*" >&2
}

die() {
    printf '%s ERROR %s\n' "$(timestamp)" "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "required command is unavailable: $1"
}

require_variable() {
    local name=$1
    [[ -n ${!name:-} ]] || die "required variable is unset: $name"
}
