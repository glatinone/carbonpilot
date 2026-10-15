#!/usr/bin/env bash
#
# scripts/deploy.sh — one command from a green local build to a live CarbonPilot.
#
# Idempotent by construction: rsync only moves files that changed, the systemd
# unit is rewritten only when its content differs from the template below, and
# the restart + health checks are safe to run any number of times. Nothing here
# touches git, the server's `.env`, or the SQLite database — code and the static
# export only.
#
# Everything host-specific comes from the environment (key auth, never a
# password — BatchMode would refuse a prompt anyway):
#
#   SSH_HOST     default 212.2.250.84                          (a0-content, Civo)
#   SSH_USER     default a0admin
#   SSH_KEY      default ""  → ssh falls back to ~/.ssh identities
#   SYSCTL_SUDO  default sudo   (set "" when already root, "sudo -n" also works)
#   PUBLIC_URL   default https://rakazo-civo.tail1b51ed.ts.net:8443 (Tailscale Funnel)
#   APP_PORT     default 8010     (loopback port the unit binds)
#   SKIP_BUILD   set to 1 to ship an existing frontend/out untouched
#
# Usage:
#   ./scripts/deploy.sh
#   SSH_KEY=/c/Users/me/keys/a0_infra_ed25519 ./scripts/deploy.sh
#
set -euo pipefail

# --- configuration ---------------------------------------------------------
SSH_HOST="${SSH_HOST:-212.2.250.84}"
SSH_USER="${SSH_USER:-a0admin}"
SSH_KEY="${SSH_KEY:-}"
SYSCTL_SUDO="${SYSCTL_SUDO:-sudo}"
PUBLIC_URL="${PUBLIC_URL:-https://rakazo-civo.tail1b51ed.ts.net:8443}"
APP_PORT="${APP_PORT:-8010}"
REMOTE_DIR="${REMOTE_DIR:-/home/a0admin/carbonpilot}"
UNIT_NAME="carbonpilot"
UNIT_PATH="/etc/systemd/system/${UNIT_NAME}.service"
SKIP_BUILD="${SKIP_BUILD:-0}"

# Repo root is the parent of scripts/, so no machine-specific path is baked in.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SSH_TARGET="$SSH_USER@$SSH_HOST"

# BatchMode: a missing key must fail fast instead of hanging on a password
# prompt this host will never answer.
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)
if [ -n "$SSH_KEY" ]; then
  SSH_OPTS+=(-i "$SSH_KEY")
fi

step() { printf '\n==> %s\n' "$*"; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# Run one command on the app host, stdout passes through.
remote() {
  ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "$@"
}

command -v ssh >/dev/null 2>&1 || die "ssh not found in PATH"
command -v curl >/dev/null 2>&1 || die "curl not found in PATH"

printf 'CarbonPilot deploy → %s (unit %s)\n' "$SSH_TARGET:$REMOTE_DIR" "$UNIT_NAME"

# --- 1. build the static UI locally ---------------------------------------
# frontend/out is the artifact the backend serves; it must be fresh or the
# deploy ships yesterday's bundle (the "stale static build" failure mode).
step "Build frontend/out (Next.js static export)"
if [ "$SKIP_BUILD" = "1" ]; then
  echo "SKIP_BUILD=1 — shipping the existing frontend/out"
else
  command -v npm >/dev/null 2>&1 || die "npm not found in PATH (or set SKIP_BUILD=1)"
  ( cd "$REPO_ROOT/frontend" && npm run build )
fi
[ -f "$REPO_ROOT/frontend/out/index.html" ] \
  || die "frontend/out/index.html missing — the export did not produce a UI"

# --- 2. sync changed files to the host ------------------------------------
# Scope is deliberate: backend/app (application code) and frontend/out (the
# built UI). Dependencies, .env and backend/carbonpilot.db never travel.
step "Sync to $SSH_TARGET:$REMOTE_DIR"
remote "mkdir -p '$REMOTE_DIR/backend' '$REMOTE_DIR/frontend'"

if command -v rsync >/dev/null 2>&1; then
  # --delete keeps the remote tree a mirror: superseded bundles and removed
  # modules disappear instead of lingering next to the new ones. Bytecode is
  # excluded because it is an artifact of this machine, not of the server.
  # The ssh flags ride inside -e; rsync splits that string shell-style, hence
  # the escaped quotes around a key path that may contain spaces.
  RSYNC_RSH="ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new"
  if [ -n "$SSH_KEY" ]; then
    RSYNC_RSH="$RSYNC_RSH -i \"$SSH_KEY\""
  fi
  ( cd "$REPO_ROOT" && rsync -a --delete \
      --exclude '__pycache__/' --exclude '*.pyc' \
      -e "$RSYNC_RSH" \
      backend/app/ "$SSH_TARGET:$REMOTE_DIR/backend/app/" )
  ( cd "$REPO_ROOT" && rsync -a --delete \
      -e "$RSYNC_RSH" \
      frontend/out/ "$SSH_TARGET:$REMOTE_DIR/frontend/out/" )
else
  # scp fallback (git-bash ships scp but not rsync): merges same-name files
  # but cannot delete stale ones, so a removal on the server still needs a
  # manual `rm`. Everything else behaves identically.
  echo "rsync not found — falling back to scp -r"
  scp -r "${SSH_OPTS[@]}" "$REPO_ROOT/backend/app" "$SSH_TARGET:$REMOTE_DIR/backend/"
  scp -r "${SSH_OPTS[@]}" "$REPO_ROOT/frontend/out" "$SSH_TARGET:$REMOTE_DIR/frontend/"
fi

# --- 3. install / update the systemd unit (only if it differs) ------------
step "systemd unit: $UNIT_PATH"
UNIT_FILE="$(mktemp)"
trap 'rm -f "$UNIT_FILE"' EXIT
# Unquoted heredoc delimiter: the only expansions are SSH_USER and REMOTE_DIR,
# so the defaults above render the exact unit currently running on the host.
cat > "$UNIT_FILE" <<EOF
[Unit]
Description=CarbonPilot — AI carbon decision engine
After=network-online.target

[Service]
User=$SSH_USER
WorkingDirectory=$REMOTE_DIR/backend
Environment=CARBONPILOT_UI_DIR=$REMOTE_DIR/frontend/out
ExecStart=$REMOTE_DIR/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port $APP_PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

if remote "cat '$UNIT_PATH' 2>/dev/null" | diff -q - "$UNIT_FILE" >/dev/null 2>&1; then
  echo "unit already matches the template — leaving it untouched"
else
  echo "unit missing or stale on host — installing"
  remote "$SYSCTL_SUDO tee '$UNIT_PATH' >/dev/null" < "$UNIT_FILE"
fi

# --- 4. reload + restart the service --------------------------------------
step "systemctl daemon-reload + restart $UNIT_NAME"
remote "$SYSCTL_SUDO systemctl daemon-reload"
remote "$SYSCTL_SUDO systemctl enable $UNIT_NAME" # no-op once enabled (idempotent)
remote "$SYSCTL_SUDO systemctl restart $UNIT_NAME"

# --- 5. health check: GET /api/health on port 8010 -------------------------
# The service binds loopback on the host, so the probe has to run there too.
# uvicorn needs a moment after restart — retry instead of failing on race.
step "Health check http://127.0.0.1:$APP_PORT/api/health (on host)"
remote "command -v curl >/dev/null 2>&1" || die "curl missing on $SSH_HOST (needed for the health check)"

HEALTH=""
for _ in $(seq 1 15); do
  if HEALTH="$(remote "curl -fsS --max-time 5 'http://127.0.0.1:$APP_PORT/api/health'" 2>/dev/null)"; then
    break
  fi
  HEALTH=""
  sleep 2
done
[ -n "$HEALTH" ] || die "no answer on port $APP_PORT after 15 attempts — check: systemctl status $UNIT_NAME"
printf '  %s\n' "$HEALTH"
echo "$HEALTH" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' \
  || die "health answered but status is not ok"
echo "$HEALTH" | grep -Eq '"ui_served"[[:space:]]*:[[:space:]]*true' \
  || die "API healthy but the static UI is not served (CARBONPILOT_UI_DIR wrong or frontend/out empty)"

# --- 6. verify the public Tailscale Funnel URL ----------------------------
# curl -k because the funnel presents its own cert chain; retries because the
# tunnel can lag a restart by a few seconds.
step "Public check $PUBLIC_URL/api/health"
PUBLIC_BODY=""
for _ in $(seq 1 10); do
  if PUBLIC_BODY="$(curl -k -fsS --max-time 20 "$PUBLIC_URL/api/health" 2>/dev/null)"; then
    break
  fi
  PUBLIC_BODY=""
  sleep 3
done
[ -n "$PUBLIC_BODY" ] || die "unreachable through the funnel — tailscale funnel status on $SSH_HOST"
printf '  %s\n' "$PUBLIC_BODY"
echo "$PUBLIC_BODY" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' \
  || die "public URL answered but status is not ok"

printf '\nDeploy OK — local health and public funnel both report status ok.\n'
