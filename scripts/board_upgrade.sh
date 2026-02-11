#!/usr/bin/env bash
#
# Board Upgrade Script for RK3588 Smart Boards
# See design.md Section 4.17 for the upgrade protocol.
#
# Usage:
#   ./scripts/board_upgrade.sh [--branch BRANCH] [--restart]
#
# This script:
#   1. Pulls the latest code from git
#   2. Installs/updates Python dependencies
#   3. Runs database migrations (alembic)
#   4. Optionally restarts the board service
#
# Environment variables:
#   KATRAIN_DIR    - Path to KaTrain installation (default: /opt/katrain)
#   KATRAIN_BRANCH - Git branch to pull (default: master)
#   KATRAIN_USER   - System user running KaTrain (default: katrain)
#   KATRAIN_SERVICE - Systemd service name (default: katrain-board)

set -euo pipefail

# ── Configuration ──
KATRAIN_DIR="${KATRAIN_DIR:-/opt/katrain}"
KATRAIN_BRANCH="${KATRAIN_BRANCH:-master}"
KATRAIN_USER="${KATRAIN_USER:-katrain}"
KATRAIN_SERVICE="${KATRAIN_SERVICE:-katrain-board}"
RESTART=false

# ── Parse Arguments ──
while [[ $# -gt 0 ]]; do
    case $1 in
        --branch)
            KATRAIN_BRANCH="$2"
            shift 2
            ;;
        --restart)
            RESTART=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--branch BRANCH] [--restart]"
            echo ""
            echo "Options:"
            echo "  --branch BRANCH  Git branch to pull (default: master)"
            echo "  --restart        Restart the board service after upgrade"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ── Helpers ──
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ── Pre-flight Checks ──
if [ ! -d "$KATRAIN_DIR" ]; then
    echo "ERROR: KaTrain directory not found: $KATRAIN_DIR"
    exit 1
fi

cd "$KATRAIN_DIR"

# ── Step 1: Pull Latest Code ──
log "Pulling latest code from branch: $KATRAIN_BRANCH"
BEFORE=$(git rev-parse HEAD)
git fetch origin
git checkout "$KATRAIN_BRANCH"
git pull origin "$KATRAIN_BRANCH"
AFTER=$(git rev-parse HEAD)

if [ "$BEFORE" = "$AFTER" ]; then
    log "Already up to date ($BEFORE)"
    exit 0
fi

log "Updated: $BEFORE -> $AFTER"
git log --oneline "${BEFORE}..${AFTER}" | head -10

# ── Step 2: Update Dependencies ──
log "Updating Python dependencies..."
if command -v uv &>/dev/null; then
    uv sync
elif [ -f requirements-web.txt ]; then
    pip install -r requirements-web.txt
else
    pip install -e .
fi

# ── Step 3: Database Migrations ──
if [ -d "alembic" ] && command -v alembic &>/dev/null; then
    log "Running database migrations..."
    alembic upgrade head
else
    log "No alembic directory found, skipping migrations"
fi

# ── Step 4: Build Frontend (if needed) ──
if [ -f "katrain/web/ui/package.json" ] && command -v npm &>/dev/null; then
    log "Building frontend..."
    cd katrain/web/ui
    npm install --production
    npm run build
    cd "$KATRAIN_DIR"
fi

# ── Step 5: Restart Service ──
if [ "$RESTART" = true ]; then
    log "Restarting $KATRAIN_SERVICE..."
    if command -v systemctl &>/dev/null; then
        sudo systemctl restart "$KATRAIN_SERVICE"
        sleep 2
        sudo systemctl status "$KATRAIN_SERVICE" --no-pager || true
    else
        log "WARNING: systemctl not available, please restart manually"
    fi
fi

log "Upgrade complete!"
