#!/usr/bin/env python3
"""SessionStart hook: inject MLflow tracing env vars if configured.

Reads tracing config from $CLAUDE_PLUGIN_DATA/tracing.json (written by
/trace-setup). If present and valid, writes env vars to $CLAUDE_ENV_FILE
so they're available for the entire session.

Silent no-op if tracing isn't configured — opt-in only.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path


def main():
    plugin_data = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    fallback = Path.home() / ".claude" / "odh-claude-tracing" / "tracing.json"

    config_path = None
    if plugin_data and (plugin_data / "tracing.json").exists():
        config_path = plugin_data / "tracing.json"
    elif fallback.exists():
        config_path = fallback

    if not config_path:
        return

    try:
        config = json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return

    uri = config.get("tracking_uri", "")
    token = config.get("token", "")
    experiment = config.get("experiment", "")
    workspace = config.get("workspace", "")

    if not uri or not token:
        return

    if not _token_valid(uri, token, workspace):
        print(
            "odh-tracing: MLflow token expired or invalid. "
            "Run /trace-setup to refresh.",
            file=sys.stderr,
        )
        return

    env_file = os.environ.get("CLAUDE_ENV_FILE", "")
    if not env_file:
        return

    with open(env_file, "a") as f:
        f.write(f"export MLFLOW_TRACKING_URI={_shell_quote(uri)}\n")
        f.write(f"export MLFLOW_TRACKING_TOKEN={_shell_quote(token)}\n")
        if experiment:
            f.write(f"export MLFLOW_EXPERIMENT_NAME={_shell_quote(experiment)}\n")
        if workspace:
            f.write(f"export MLFLOW_WORKSPACE={_shell_quote(workspace)}\n")
            f.write("export MLFLOW_ENABLE_WORKSPACES='true'\n")


def _token_valid(uri, token, workspace=""):
    """Quick check: can we reach MLflow with this token?"""
    url = uri.rstrip("/") + "/api/2.0/mlflow/experiments/search"
    body = json.dumps({"max_results": 1}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    if workspace:
        req.add_header("X-Mlflow-Workspace", workspace)
    try:
        urllib.request.urlopen(req, timeout=5)
        return True
    except urllib.error.HTTPError as e:
        return e.code not in (401, 403)
    except Exception:
        return True


def _shell_quote(s):
    return "'" + s.replace("'", "'\\''") + "'"


if __name__ == "__main__":
    main()
