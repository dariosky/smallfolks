#!/usr/bin/env bash
# Generic OpalStack deploy script for Smallfolk.
# Builds frontend assets locally, updates a remote git checkout, uploads an
# optional production env file and secret files, optionally provisions
# start/watch helpers, runs setup/migrations, and restarts.

set -euo pipefail

is_true() {
  local value="${1:-}"
  value=$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')
  case "$value" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

REMOTE=${REMOTE:-my-server}
BRANCH=${BRANCH:-main}
REQUIRED_LOCAL_BRANCH=${REQUIRED_LOCAL_BRANCH-main}
LOCAL_ENV_FILE=${LOCAL_ENV_FILE:-}
LOCAL_SECRET_FILES=${LOCAL_SECRET_FILES:-}
REMOTE_APP_NAME=${REMOTE_APP_NAME:-smallfolk}
REMOTE_REPO_DIR=${REMOTE_REPO_DIR:-\~/src/smallfolk}
REMOTE_WORK_DIR=${REMOTE_WORK_DIR:-$REMOTE_REPO_DIR/backend}
REMOTE_BIND_HOST=${REMOTE_BIND_HOST:-127.0.0.1}
REMOTE_PORT=${REMOTE_PORT:-5341}
REMOTE_UVICORN_APP=${REMOTE_UVICORN_APP:-app:create_app}
REMOTE_UVICORN_FACTORY=${REMOTE_UVICORN_FACTORY:-true}
REMOTE_APP_DIR=${REMOTE_APP_DIR:-\$HOME/apps/$REMOTE_APP_NAME}
REMOTE_LOG_DIR=${REMOTE_LOG_DIR:-\$HOME/logs/apps/$REMOTE_APP_NAME}
REMOTE_SECRET_DIR=${REMOTE_SECRET_DIR:-$REMOTE_APP_DIR/secrets}
REMOTE_START_SCRIPT=${REMOTE_START_SCRIPT:-\$HOME/bin/$REMOTE_APP_NAME-start.sh}
REMOTE_WATCH_SCRIPT=${REMOTE_WATCH_SCRIPT:-\$HOME/bin/$REMOTE_APP_NAME-watch.sh}
REMOTE_START_COMMAND=${REMOTE_START_COMMAND:-\$HOME/bin/smallfolk-start.sh}
PROVISION_WATCHDOG=${PROVISION_WATCHDOG:-true}
INSTALL_CRON_WATCH=${INSTALL_CRON_WATCH:-false}
CRON_SCHEDULE=${CRON_SCHEDULE:-* * * * *}
PY_VERSION=${PY_VERSION:-3.13}

FRONTEND_DIR=${FRONTEND_DIR:-frontend}
FRONTEND_BUILD_DIR=${FRONTEND_BUILD_DIR:-frontend/dist}
FRONTEND_INSTALL_COMMAND=${FRONTEND_INSTALL_COMMAND:-}
FRONTEND_BUILD_COMMAND=${FRONTEND_BUILD_COMMAND:-npm run build}
REMOTE_SYNC_FRONTEND=${REMOTE_SYNC_FRONTEND:-1}

REMOTE_SETUP_COMMAND=${REMOTE_SETUP_COMMAND:-uv sync}
REMOTE_MIGRATION_COMMAND=${REMOTE_MIGRATION_COMMAND:-(cd backend && uv run alembic -c alembic.ini upgrade head)}

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
REPO_URL=${REPO_URL:-$(git -C "$REPO_ROOT" remote get-url origin)}

CURRENT_BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
if [[ -n "$REQUIRED_LOCAL_BRANCH" && "$CURRENT_BRANCH" != "$REQUIRED_LOCAL_BRANCH" ]]; then
  echo "ERROR: Deploys must be run from the $REQUIRED_LOCAL_BRANCH branch. Current branch: ${CURRENT_BRANCH:-detached HEAD}." >&2
  exit 1
fi

if [[ -n "$REQUIRED_LOCAL_BRANCH" ]]; then
  git -C "$REPO_ROOT" fetch origin "+refs/heads/$REQUIRED_LOCAL_BRANCH:refs/remotes/origin/$REQUIRED_LOCAL_BRANCH"
  UNPUSHED_COMMITS=$(git -C "$REPO_ROOT" rev-list --count "origin/$REQUIRED_LOCAL_BRANCH..HEAD")
  if (( UNPUSHED_COMMITS > 0 )); then
    echo "ERROR: Refusing to deploy with $UNPUSHED_COMMITS unpushed commit(s) on $REQUIRED_LOCAL_BRANCH." >&2
    echo "Push your commits first, then rerun deploy." >&2
    exit 1
  fi
fi

if ! ssh -q -o BatchMode=yes -o ConnectTimeout=5 "$REMOTE" exit; then
  echo "ERROR: Unable to connect to $REMOTE." >&2
  exit 1
fi

REMOTE_HOME=$(ssh "$REMOTE" 'printf %s "$HOME"')
resolve_remote_path() {
  local path=$1
  case "$path" in
    "~") printf '%s\n' "$REMOTE_HOME" ;;
    "~/"*) printf '%s/%s\n' "$REMOTE_HOME" "${path#\~/}" ;;
    "\$HOME") printf '%s\n' "$REMOTE_HOME" ;;
    "\$HOME/"*) printf '%s/%s\n' "$REMOTE_HOME" "${path#\$HOME/}" ;;
    "\${HOME}") printf '%s\n' "$REMOTE_HOME" ;;
    "\${HOME}/"*) printf '%s/%s\n' "$REMOTE_HOME" "${path#\${HOME}/}" ;;
    *) printf '%s\n' "$path" ;;
  esac
}

read_env_value() {
  local file=$1
  local name=$2
  local line value
  line=$(grep -E "^${name}=" "$file" | tail -n 1 || true)
  if [[ -z "$line" ]]; then
    return 0
  fi
  value=${line#*=}
  value=${value%$'\r'}
  if [[ "$value" == \"*\" && "$value" == *\" ]]; then
    value=${value#\"}
    value=${value%\"}
  elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
    value=${value#\'}
    value=${value%\'}
  fi
  printf '%s\n' "$value"
}

REMOTE_REPO_DIR_RESOLVED=$(resolve_remote_path "$REMOTE_REPO_DIR")
REMOTE_WORK_DIR_RESOLVED=$(resolve_remote_path "$REMOTE_WORK_DIR")
REMOTE_APP_DIR_RESOLVED=$(resolve_remote_path "$REMOTE_APP_DIR")
REMOTE_LOG_DIR_RESOLVED=$(resolve_remote_path "$REMOTE_LOG_DIR")
REMOTE_SECRET_DIR_RESOLVED=$(resolve_remote_path "$REMOTE_SECRET_DIR")
REMOTE_START_SCRIPT_RESOLVED=$(resolve_remote_path "$REMOTE_START_SCRIPT")
REMOTE_WATCH_SCRIPT_RESOLVED=$(resolve_remote_path "$REMOTE_WATCH_SCRIPT")
REMOTE_START_COMMAND_RESOLVED=$(resolve_remote_path "$REMOTE_START_COMMAND")

ssh "$REMOTE" bash -s -- \
  "$REMOTE_REPO_DIR_RESOLVED" "$REMOTE_APP_NAME" "$BRANCH" "$REPO_URL" <<'EOF'
set -euo pipefail
remote_repo_dir=$1
remote_app_name=$2
branch=$3
repo_url=$4

mkdir -p "$(dirname "$remote_repo_dir")" "$HOME/apps/$remote_app_name"
if [[ -d "$remote_repo_dir/.git" ]]; then
  cd "$remote_repo_dir"
  git fetch origin "$branch"
  git checkout "$branch"
  git reset --hard "origin/$branch"
else
  if [[ -e "$remote_repo_dir" ]]; then
    echo "ERROR: $remote_repo_dir exists but is not a git checkout." >&2
    exit 1
  fi
  git clone --depth=1 --branch "$branch" "$repo_url" "$remote_repo_dir"
fi
mkdir -p "$remote_repo_dir/frontend/dist"
EOF

if [[ -n "$LOCAL_ENV_FILE" && -f "$REPO_ROOT/$LOCAL_ENV_FILE" ]]; then
  echo "Uploading env file to remote backend/.env"
  scp "$REPO_ROOT/$LOCAL_ENV_FILE" "$REMOTE:$REMOTE_REPO_DIR_RESOLVED/backend/.env"
elif [[ -n "$LOCAL_ENV_FILE" ]]; then
  echo "ERROR: Env file $LOCAL_ENV_FILE not found." >&2
  exit 1
else
  echo "No LOCAL_ENV_FILE specified; skipping env upload."
fi

if [[ -n "$LOCAL_SECRET_FILES" ]]; then
  ssh "$REMOTE" "mkdir -p '$REMOTE_SECRET_DIR_RESOLVED'"
  for secret_file in $LOCAL_SECRET_FILES; do
    if [[ ! -f "$REPO_ROOT/$secret_file" ]]; then
      echo "ERROR: Secret file $secret_file not found." >&2
      exit 1
    fi
    echo "Uploading secret file $(basename "$secret_file")"
    scp "$REPO_ROOT/$secret_file" \
      "$REMOTE:$REMOTE_SECRET_DIR_RESOLVED/$(basename "$secret_file")"
  done
fi

if [[ -d "$REPO_ROOT/$FRONTEND_DIR" ]]; then
  if command -v corepack >/dev/null 2>&1; then
    corepack enable || true
  fi

  if [[ -n "$LOCAL_ENV_FILE" && -f "$REPO_ROOT/$LOCAL_ENV_FILE" ]]; then
    if [[ -z "${VITE_GA_MEASUREMENT_ID:-}" && -z "${GA_MEASUREMENT_ID:-}" ]]; then
      LOCAL_GA_MEASUREMENT_ID=$(read_env_value "$REPO_ROOT/$LOCAL_ENV_FILE" VITE_GA_MEASUREMENT_ID)
      if [[ -z "$LOCAL_GA_MEASUREMENT_ID" ]]; then
        LOCAL_GA_MEASUREMENT_ID=$(read_env_value "$REPO_ROOT/$LOCAL_ENV_FILE" GA_MEASUREMENT_ID)
      fi
      if [[ -n "$LOCAL_GA_MEASUREMENT_ID" ]]; then
        export VITE_GA_MEASUREMENT_ID="$LOCAL_GA_MEASUREMENT_ID"
        echo "Using GA measurement ID from $LOCAL_ENV_FILE for frontend build."
      fi
    fi
    if [[ -z "${VITE_GOOGLE_CLIENT_ID:-}" && -z "${GOOGLE_CLIENT_ID:-}" ]]; then
      LOCAL_GOOGLE_CLIENT_ID=$(read_env_value "$REPO_ROOT/$LOCAL_ENV_FILE" VITE_GOOGLE_CLIENT_ID)
      if [[ -z "$LOCAL_GOOGLE_CLIENT_ID" ]]; then
        LOCAL_GOOGLE_CLIENT_ID=$(read_env_value "$REPO_ROOT/$LOCAL_ENV_FILE" GOOGLE_CLIENT_ID)
      fi
      if [[ -n "$LOCAL_GOOGLE_CLIENT_ID" ]]; then
        export VITE_GOOGLE_CLIENT_ID="$LOCAL_GOOGLE_CLIENT_ID"
        echo "Using Google client ID from $LOCAL_ENV_FILE for frontend build."
      fi
    fi
  fi

  cd "$REPO_ROOT/$FRONTEND_DIR"
  if [[ -n "$FRONTEND_INSTALL_COMMAND" ]]; then
    eval "$FRONTEND_INSTALL_COMMAND"
  elif [[ -f package-lock.json ]]; then
    npm ci --no-fund
  elif [[ -f package.json ]]; then
    npm install --no-fund
  fi
  eval "$FRONTEND_BUILD_COMMAND"

  if [[ "$REMOTE_SYNC_FRONTEND" == "1" ]]; then
    echo "Syncing built frontend to remote checkout..."
    rsync -a --delete "$REPO_ROOT/$FRONTEND_BUILD_DIR/" "$REMOTE:$REMOTE_REPO_DIR_RESOLVED/$FRONTEND_BUILD_DIR/"
  fi
fi

if is_true "$PROVISION_WATCHDOG"; then
  factory_flag=""
  if is_true "$REMOTE_UVICORN_FACTORY"; then
    factory_flag="--factory"
  fi
  ssh "$REMOTE" bash -s -- \
    "$REMOTE_APP_NAME" "$REMOTE_REPO_DIR_RESOLVED" "$REMOTE_WORK_DIR_RESOLVED" \
    "$REMOTE_APP_DIR_RESOLVED" "$REMOTE_LOG_DIR_RESOLVED" \
    "$REMOTE_START_SCRIPT_RESOLVED" "$REMOTE_WATCH_SCRIPT_RESOLVED" \
    "$REMOTE_BIND_HOST" "$REMOTE_PORT" "$REMOTE_UVICORN_APP" "$factory_flag" <<'EOF'
set -euo pipefail
app_name=$1
repo_dir=$2
work_dir=$3
app_dir=$4
log_dir=$5
start_script=$6
watch_script=$7
bind_host=$8
port=$9
uvicorn_app=${10}
factory_flag=${11}

mkdir -p "$app_dir" "$log_dir" "$(dirname "$start_script")"
cat > "$start_script" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
PID_FILE="$app_dir/uvicorn.pid"
LOG_FILE="$log_dir/$app_name.log"
STOP_WAIT_SECONDS=10

if [[ -f "\$PID_FILE" ]]; then
  PID=\$(cat "\$PID_FILE" 2>/dev/null || true)
  if [[ -n "\$PID" ]] && kill -0 "\$PID" >/dev/null 2>&1; then
    kill "\$PID" || true
    waited=0
    while kill -0 "\$PID" >/dev/null 2>&1; do
      if (( waited >= STOP_WAIT_SECONDS )); then
        kill -KILL "\$PID" || true
        break
      fi
      sleep 1
      waited=\$((waited + 1))
    done
  fi
  rm -f "\$PID_FILE"
fi

source "$repo_dir/.venv/bin/activate"
cd "$work_dir"
nohup python -m uvicorn "$uvicorn_app" --host "$bind_host" --port "$port" $factory_flag \
  > "\$LOG_FILE" 2>&1 &
PID=\$!
echo \$PID > "\$PID_FILE"
sleep 1
kill -0 "\$PID" >/dev/null 2>&1
echo "Started $app_name on $bind_host:$port (PID \$PID)"
SCRIPT
chmod +x "$start_script"

cat > "$watch_script" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
PID_FILE="$app_dir/uvicorn.pid"
LOG_FILE="$log_dir/watch.log"
if [[ -f "\$PID_FILE" ]]; then
  PID=\$(cat "\$PID_FILE" 2>/dev/null || true)
  if [[ -n "\$PID" ]] && kill -0 "\$PID" >/dev/null 2>&1; then
    exit 0
  fi
  echo "\$(date '+%F %T') process with pid \$PID not running, restarting..." >> "\$LOG_FILE"
else
  echo "\$(date '+%F %T') pid file not found, starting process..." >> "\$LOG_FILE"
fi
"$start_script" >> "\$LOG_FILE" 2>&1
SCRIPT
chmod +x "$watch_script"
EOF
fi

if is_true "$INSTALL_CRON_WATCH"; then
  ssh "$REMOTE" "set -euo pipefail; current=\$(crontab -l 2>/dev/null || true); entry='$CRON_SCHEDULE $REMOTE_WATCH_SCRIPT_RESOLVED'; if ! printf '%s\n' \"\$current\" | grep -Fqx \"\$entry\"; then { printf '%s\n' \"\$current\"; printf '%s\n' \"\$entry\"; } | sed '/^$/N;/^\n$/D' | crontab -; fi"
fi

printf -v REMOTE_REPO_DIR_QUOTED "%q" "$REMOTE_REPO_DIR_RESOLVED"
printf -v PY_VERSION_QUOTED "%q" "$PY_VERSION"
printf -v REMOTE_SETUP_COMMAND_QUOTED "%q" "$REMOTE_SETUP_COMMAND"
printf -v REMOTE_MIGRATION_COMMAND_QUOTED "%q" "$REMOTE_MIGRATION_COMMAND"
printf -v REMOTE_START_COMMAND_QUOTED "%q" "$REMOTE_START_COMMAND_RESOLVED"

ssh "$REMOTE" bash -s <<EOF
set -euo pipefail
remote_repo_dir=$REMOTE_REPO_DIR_QUOTED
py_version=$PY_VERSION_QUOTED
setup_command=$REMOTE_SETUP_COMMAND_QUOTED
migration_command=$REMOTE_MIGRATION_COMMAND_QUOTED
start_command=$REMOTE_START_COMMAND_QUOTED

cd "\$remote_repo_dir"
if [[ ! -d .venv ]]; then
  "python\${py_version}" -m venv .venv
fi
source .venv/bin/activate
eval "\$setup_command"
if [[ -n "\$migration_command" ]]; then
  eval "\$migration_command"
fi
eval "\$start_command"
EOF

echo "Deployment complete."
