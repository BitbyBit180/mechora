#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/venv/bin/python}"
CELERY_BIN="${CELERY_BIN:-$PROJECT_DIR/venv/bin/celery}"

# run.sh is the local development launcher. Ensure Django serves app static
# files even when the shell environment contains a production-style DEBUG value.
export DEBUG=true

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || command -v python)"
fi
if [[ ! -x "$CELERY_BIN" ]]; then
  CELERY_BIN="$(command -v celery)"
fi

if ! command -v redis-cli >/dev/null 2>&1; then
  echo "redis-cli was not found. Install Redis before running this script."
  exit 1
fi

open_terminal() {
  local title="$1"
  local command="$2"
  local project_q
  local log_name
  printf -v project_q '%q' "$PROJECT_DIR"
  log_name="${title//[^[:alnum:]_-]/_}"

  if command -v gnome-terminal >/dev/null 2>&1; then
    # Launch asynchronously. Some GNOME installations abort while loading
    # an invalid desktop setting; that must not terminate this launcher.
    gnome-terminal --title="$title" -- bash -lc "cd $project_q && $command; status=\$?; echo; echo '$title stopped with status' \$status; exec bash" \
      >"${TMPDIR:-/tmp}/mechora-${log_name}.log" 2>&1 &
    disown 2>/dev/null || true
  elif command -v konsole >/dev/null 2>&1; then
    konsole --new-tab -p tabtitle="$title" -e bash -lc "cd $project_q && $command; exec bash" >/dev/null 2>&1 &
  elif command -v xfce4-terminal >/dev/null 2>&1; then
    xfce4-terminal --title="$title" --command="bash -lc 'cd $project_q && $command; exec bash'" >/dev/null 2>&1 &
  elif command -v x-terminal-emulator >/dev/null 2>&1; then
    x-terminal-emulator -T "$title" -e bash -lc "cd $project_q && $command; exec bash" >/dev/null 2>&1 &
  else
    echo "No supported terminal emulator found. Run these commands manually:"
    echo "  redis-server"
    echo "  $CELERY_BIN -A mechora worker --loglevel=INFO"
    echo "  $PYTHON_BIN manage.py runserver"
    exit 1
  fi
}

if redis-cli ping >/dev/null 2>&1; then
  open_terminal "MECHORA Redis" "echo 'Redis is already running'; redis-cli ping"
else
  open_terminal "MECHORA Redis" "redis-server"
  for _ in {1..15}; do
    if redis-cli ping >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

if ! redis-cli ping >/dev/null 2>&1; then
  echo "Redis did not become ready. Celery and Django were not started."
  exit 1
fi

open_terminal "MECHORA Celery" "$(printf '%q' "$CELERY_BIN") -A mechora worker --loglevel=INFO"
open_terminal "MECHORA Django" "$(printf '%q' "$PYTHON_BIN") manage.py runserver"

echo "Started Redis, Celery, and Django in separate terminal windows."
