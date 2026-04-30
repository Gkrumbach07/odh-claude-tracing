#!/usr/bin/env python3
"""Configure MLflow production tracing.

Manages tracing config stored in $CLAUDE_PLUGIN_DATA/tracing.json.
Used by the /trace-setup skill and the SessionStart hook.
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

DEFAULTS = {
    "tracking_uri": "https://rh-ai.apps.rosa.ui-razzmatazz.swih.p3.openshiftapps.com/mlflow",
    "experiment": "odh-dashboard-skills",
    "workspace": "",
}


def config_path():
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    if plugin_data:
        return Path(plugin_data) / "tracing.json"
    return Path.home() / ".claude" / "odh-claude-tracing" / "tracing.json"


def load_config(path=None):
    p = path or config_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(config, path=None):
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(config, indent=2) + "\n")


def test_connection(uri, token, workspace=""):
    """Test MLflow connectivity. Returns (ok, message)."""
    url = uri.rstrip("/") + "/api/2.0/mlflow/experiments/search"
    body = json.dumps({"max_results": 5}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    if workspace:
        req.add_header("X-Mlflow-Workspace", workspace)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        experiments = data.get("experiments", [])
        names = [e.get("name", "") for e in experiments[:5]]
        return True, f"Connected. {len(experiments)} experiments: {', '.join(names)}"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, "Authentication failed — token expired or invalid"
        body_text = ""
        try:
            body_text = e.read().decode()[:200]
        except Exception:
            pass
        if "login" in body_text.lower() or "html" in body_text.lower():
            return False, "Got login page — token not accepted"
        return False, f"HTTP {e.code}: {body_text}"
    except Exception as e:
        return False, f"Connection failed: {str(e)[:200]}"


def do_setup(args):
    if not args.token:
        print("ERROR: --token is required", file=sys.stderr)
        return 1

    uri = args.uri or DEFAULTS["tracking_uri"]
    experiment = args.experiment or DEFAULTS["experiment"]
    workspace = args.workspace or DEFAULTS["workspace"]

    ok, msg = test_connection(uri, args.token, workspace)
    if not ok:
        print(f"CONNECTION_FAILED: {msg}", file=sys.stderr)
        return 2

    config = {
        "tracking_uri": uri,
        "token": args.token,
        "experiment": experiment,
        "workspace": workspace,
    }
    save_config(config)

    p = config_path()
    print(f"OK: Tracing configured at {p}")
    print(f"  URI: {uri}")
    print(f"  Experiment: {experiment}")
    print(f"  Connection: {msg}")
    return 0


def do_remove(args):
    p = config_path()
    if p.exists():
        p.unlink()
        print(f"OK: Tracing config removed ({p})")
    else:
        print("OK: Tracing was not configured")
    return 0


def do_status(args):
    config = load_config()
    uri = config.get("tracking_uri", "")
    token = config.get("token", "")
    experiment = config.get("experiment", "")
    workspace = config.get("workspace", "")

    result = {
        "configured": bool(uri and token),
        "tracking_uri": uri,
        "token_set": bool(token),
        "token_preview": f"{token[:8]}...{token[-4:]}" if len(token) > 12 else "",
        "experiment": experiment,
        "workspace": workspace,
        "config_path": str(config_path()),
    }

    if uri and token:
        ok, msg = test_connection(uri, token, workspace)
        result["connected"] = ok
        result["connection_message"] = msg
    else:
        result["connected"] = False
        result["connection_message"] = "Not configured"

    print(json.dumps(result, indent=2))
    return 0 if result.get("connected") else 1


def main():
    parser = argparse.ArgumentParser(description="Configure MLflow tracing")
    parser.add_argument("action", choices=["setup", "remove", "status"])
    parser.add_argument("--uri", default="")
    parser.add_argument("--token", default="")
    parser.add_argument("--experiment", default="")
    parser.add_argument("--workspace", default="")
    args = parser.parse_args()

    actions = {"setup": do_setup, "remove": do_remove, "status": do_status}
    sys.exit(actions[args.action](args))


if __name__ == "__main__":
    main()
