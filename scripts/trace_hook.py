#!/usr/bin/env python3
"""Stop hook: log MLflow trace if tracing is configured.

Thin wrapper around mlflow.claude_code.hooks.stop_hook_handler().
No-op if MLFLOW_TRACKING_URI is not set or mlflow is not installed.
"""

import os
import sys


def main():
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        return

    try:
        from mlflow.claude_code.hooks import stop_hook_handler
        stop_hook_handler()
    except ImportError:
        pass
    except Exception as e:
        print(f"odh-tracing: trace hook error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
