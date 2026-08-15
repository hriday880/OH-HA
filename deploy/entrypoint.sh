#!/bin/sh
# ==============================================================================
# OpenHuman & Hermes Bot Container Entrypoint
# Dynamically configures Git authentication, verifies environment variables,
# initializes/clones the remote Obsidian vault, and executes the application.
# ==============================================================================

set -e

echo "=== Starting OpenHuman & Hermes Telegram Companion ==="
echo "Runtime User: $(whoami) (UID: $(id -u))"
echo "Environment: ${ENVIRONMENT:-production}"
echo "Keepalive Port: ${PORT:-8080}"

# 1. Global Git Safe Directory and Author Configuration
git config --global --add safe.directory "*" || true
git config --global --add safe.directory "${VAULT_PATH:-/app/vault}" || true
git config --global user.name "${GIT_AUTHOR_NAME:-OpenHuman Hermes Bot}"
git config --global user.email "${GIT_AUTHOR_EMAIL:-bot@openhuman.local}"

# 2. Dynamic SSH Deploy Key Configuration
SSH_DIR="${HOME:-/home/botuser}/.ssh"
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

if [ -n "${GIT_SSH_KEY:-}" ]; then
    echo "Configuring SSH deploy key for Git synchronization..."
    DEPLOY_KEY_FILE="$SSH_DIR/id_deploy_rsa"
    if [ -f "$GIT_SSH_KEY" ]; then
        cp "$GIT_SSH_KEY" "$DEPLOY_KEY_FILE"
    else
        # Key passed as inline raw string
        printf "%s\n" "$GIT_SSH_KEY" > "$DEPLOY_KEY_FILE"
    fi
    chmod 600 "$DEPLOY_KEY_FILE"
    export GIT_SSH_COMMAND="ssh -i $DEPLOY_KEY_FILE -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
fi

# 3. Remote URL & Authentication Resolution
REMOTE_URL="${GIT_REMOTE_URL:-${OBSIDIAN_GIT_REPO_URL:-}}"
AUTH_URL="$REMOTE_URL"

if [ -n "$REMOTE_URL" ]; then
    if [ -n "${GIT_AUTH_TOKEN:-}" ] && echo "$REMOTE_URL" | grep -q "^https://"; then
        # Inject HTTPS PAT token safely without exposing in output
        CLEAN_URL=$(echo "$REMOTE_URL" | sed 's|^https://||')
        # If remote contains user@, strip it
        CLEAN_URL=$(echo "$CLEAN_URL" | sed 's|^[^@]*@||')
        AUTH_URL="https://${GIT_AUTH_TOKEN}@${CLEAN_URL}"
    fi
fi

# 4. Vault Directory & Initial Git Clone/Pull
VAULT_DIR="${VAULT_PATH:-/app/vault}"
mkdir -p "$VAULT_DIR"

if [ -n "$REMOTE_URL" ]; then
    BRANCH="${GIT_BRANCH:-main}"
    if [ ! -d "$VAULT_DIR/.git" ]; then
        echo "Cloning remote Obsidian vault from repository into $VAULT_DIR (branch: $BRANCH)..."
        git clone --branch "$BRANCH" "$AUTH_URL" "$VAULT_DIR" || {
            echo "Initial clone failed or branch not found, attempting default branch clone..."
            git clone "$AUTH_URL" "$VAULT_DIR" || echo "Warning: Initial git clone failed. Bot will proceed and retry during runtime sync."
        }
    else
        echo "Existing Git repository found in $VAULT_DIR. Configuring remote origin..."
        (
            cd "$VAULT_DIR"
            git remote set-url origin "$AUTH_URL" 2>/dev/null || git remote add origin "$AUTH_URL" 2>/dev/null || true
            git fetch origin "$BRANCH" 2>/dev/null || true
        )
    fi
fi

# 5. Production Environment Validation Warnings
if [ "${ENVIRONMENT:-production}" = "production" ]; then
    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
        echo "[WARNING] TELEGRAM_BOT_TOKEN is not set. Telegram bot will fail to connect."
    fi
    if [ -z "${ALLOWED_TELEGRAM_USER_IDS:-}" ]; then
        echo "[WARNING] ALLOWED_TELEGRAM_USER_IDS is not set. In production mode, requests from all users will be rejected for vault security."
    fi
fi

# 6. Execute Application Entrypoint
echo "=== Initialization Complete. Handing off to Application Daemon ==="
if [ $# -eq 0 ]; then
    exec python -m bot.main
else
    exec "$@"
fi
