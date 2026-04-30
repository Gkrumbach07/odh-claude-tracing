#!/bin/bash
# Ensure the plugin's Python venv exists with mlflow installed.
# Called by SessionStart hook before init_tracing.py.
# Creates the venv on first run, then skips on subsequent starts.

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$PLUGIN_ROOT/.venv"
STAMP_FILE="$VENV_DIR/.installed"

if [ -f "$STAMP_FILE" ] && [ -x "$VENV_DIR/bin/python3" ]; then
    exit 0
fi

python3 -m venv "$VENV_DIR" 2>/dev/null || exit 0
"$VENV_DIR/bin/pip" install -q "mlflow[genai]>=3.5" 2>/dev/null || exit 0
touch "$STAMP_FILE"
