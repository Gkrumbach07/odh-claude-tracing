---
name: trace-setup
description: Set up MLflow production tracing for Claude Code skills. Captures traces (tool calls, LLM interactions, timing, cost) and sends them to the team's shared MLflow instance. Use when asked to enable tracing, set up MLflow, track skill metrics, or opt into production monitoring.
allowed-tools: Bash, Read, AskUserQuestion
argument-hint: "[--status | --disable | --tracking-uri <uri> --experiment <name>]"
---

# Production Tracing Setup

One-command setup for MLflow tracing using `mlflow autolog claude`. Everything is written to `settings.local.json` so nothing gets committed.

## Prerequisites

- **Python >= 3.11** — required by mlflow
- **`oc` CLI** (optional) — for browser-based SSO auth. Install from the [OpenShift console](https://console-openshift-console.apps.rosa.ui-razzmatazz.swih.p3.openshiftapps.com) → **?** → **Command line tools**. Without `oc`, you can paste a token manually.

## Constants

| Constant | Value |
|----------|-------|
| MLFLOW_URI | `https://rh-ai.apps.rosa.ui-razzmatazz.swih.p3.openshiftapps.com/mlflow` |
| ROSA_API | `https://api.ui-razzmatazz.swih.p3.openshiftapps.com:443` |
| ROSA_CONSOLE | `https://console-openshift-console.apps.rosa.ui-razzmatazz.swih.p3.openshiftapps.com` |
| DEFAULT_EXPERIMENT | `odh-dashboard-skills` |
| DEFAULT_WORKSPACE | `mlflow-agent-eval-harness` |

## Step 0: Parse Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--status` | false | Check current tracing status and exit |
| `--disable` | false | Disable tracing and exit |
| `--tracking-uri <uri>` | `MLFLOW_URI` | Override MLflow server |
| `--experiment <name>` | `DEFAULT_EXPERIMENT` | MLflow experiment |

## Step 1: Handle --status

Check `.claude/settings.local.json` for tracing config (env vars and hooks). Report whether tracing is configured and what the settings are. Exit after reporting.

## Step 2: Handle --disable

Read `.claude/settings.local.json`, remove the `MLFLOW_*` env vars, the Stop hook, and the SessionStart hook (the tracing status check), write it back. Tell the user to restart Claude Code. Exit.

## Step 3: Present the plan and confirm

**Do NOT start doing things yet.** Present what will happen:

> **MLflow Tracing Setup**
>
> This will:
> 1. Ensure `mlflow` is installed (in project `.venv` if needed)
> 2. Authenticate to the ROSA cluster (opens browser for SSO — your current `oc` context is NOT affected)
> 3. Run `mlflow autolog claude` to generate the tracing hook config
> 4. Move everything to `.claude/settings.local.json` (never committed)
> 5. Restore `.claude/settings.json` to its original state
>
> **Prerequisites:** Python >= 3.11
>
> After setup, restart Claude Code and all interactions will be traced to:
> `MLFLOW_URI` (experiment: `DEFAULT_EXPERIMENT`)
>
> **Proceed?**

Use AskUserQuestion with Yes/No. If No, exit.

## Step 4: Ensure mlflow is installed

Check for mlflow on PATH or in a local venv:

```bash
which mlflow 2>/dev/null || .venv/bin/mlflow --version 2>/dev/null
```

If not found, create a venv and install. Use `uv` if available (faster), otherwise `python3 -m venv`:

```bash
# Prefer uv if available
which uv 2>/dev/null && echo "UV" || echo "PIP"
```

With uv:
```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python3 "mlflow[genai]>=3.5"
```

Without uv:
```bash
python3 -m venv .venv
.venv/bin/pip install -q "mlflow[genai]>=3.5"
```

Store the mlflow path as `MLFLOW_CMD` (either `mlflow` or `.venv/bin/mlflow`). Use the **absolute path** for `.venv/bin/mlflow` since hooks run in a bare shell without PATH modifications.

## Step 5: Authenticate to ROSA

Get an OpenShift bearer token using a throwaway kubeconfig.

```bash
which oc 2>/dev/null && echo "OC_AVAILABLE" || echo "OC_MISSING"
```

### Path A: oc available

```bash
TMPKUBE=$(mktemp)
KUBECONFIG=$TMPKUBE oc login --web https://api.ui-razzmatazz.swih.p3.openshiftapps.com:443
TOKEN=$(KUBECONFIG=$TMPKUBE oc whoami --show-token)
rm -f $TMPKUBE
```

**Use the same temp file for both commands.** Do NOT call `mktemp` twice.

If `oc login` fails with a connection error, check the ROSA API URL is correct and the cluster is reachable.

### Path B: oc not available

> `oc` CLI not found. You can either:
>
> **Install oc:** Open the [ROSA console](https://console-openshift-console.apps.rosa.ui-razzmatazz.swih.p3.openshiftapps.com) → **?** (help) → **Command line tools** → download for your OS.
>
> **Or paste a token manually:**
> 1. Open: `ROSA_CONSOLE`
> 2. Log in → click your username (top right) → **"Copy login command"** → **"Display Token"**
> 3. Paste the API token below

Use AskUserQuestion to collect the token.

## Step 6: Generate config and move to settings.local.json

### 6a: Snapshot settings.json before mlflow writes to it

```bash
cp .claude/settings.json .claude/settings.json.bak 2>/dev/null || true
```

### 6b: Run mlflow autolog claude

```bash
$MLFLOW_CMD autolog claude \
  -u <tracking_uri> \
  -n <experiment>
```

This writes `env` (MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME, MLFLOW_CLAUDE_TRACING_ENABLED) and `hooks.Stop` to `.claude/settings.json`.

### 6c: Move config to settings.local.json

Read `.claude/settings.json` (what mlflow just wrote). Read `.claude/settings.local.json` (existing local config). Merge the mlflow entries into settings.local.json:

1. Copy the entire `hooks` block from settings.json into settings.local.json
2. Copy the `env` block entries from settings.json into settings.local.json's `env`
3. Add these additional env vars to settings.local.json:
   - `MLFLOW_TRACKING_TOKEN`: `<token from Step 5>`
   - `MLFLOW_WORKSPACE`: `DEFAULT_WORKSPACE`
   - `MLFLOW_ENABLE_WORKSPACES`: `true`
4. If the hook command is bare `mlflow autolog claude stop-hook` but mlflow is only in `.venv/bin/`, replace `mlflow` with the absolute path (e.g., `/Users/me/project/.venv/bin/mlflow autolog claude stop-hook`)
5. Add a `SessionStart` hook that shows tracing status on session start. Use the same `$MLFLOW_CMD` path (absolute if from venv):

```json
"SessionStart": [
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "command": "<absolute_mlflow_path> autolog claude --status"
      }
    ]
  }
]
```

This prints the tracing connection status every time Claude Code starts, so users know tracing is active and whether the token is still valid.

### 6d: Restore settings.json

```bash
if [ -f .claude/settings.json.bak ]; then
  mv .claude/settings.json.bak .claude/settings.json
else
  rm -f .claude/settings.json
fi
```

Restore the original. If settings.json didn't exist before, remove the one mlflow created.

## Step 7: Report

> **Tracing enabled.**
> - MLflow: `<uri>` (experiment: `<experiment>`, workspace: `<workspace>`)
> - Config: `.claude/settings.local.json` (not committed)
> - **Restart Claude Code** for the hook to take effect
>
> Token expires in ~24h. Re-run `/trace-setup` to refresh.
> Run `/trace-setup --status` to check, `/trace-setup --disable` to turn off.

## Rules

- **Everything in settings.local.json** — never leave mlflow config in settings.json
- **Present plan first, then execute** — show what will happen, get yes/no, then run
- **Backup and restore settings.json** — snapshot before mlflow writes, restore after moving config
- **Never switch oc context** — always `KUBECONFIG=$(mktemp)`, reuse the same tempfile
- **Use absolute paths in hooks** — the Stop hook runs in a bare shell, `.venv/bin/mlflow` won't resolve without the full path
- **Prefer uv over pip** — faster venv creation and install
- **Run everything automatically** — only interaction is the initial yes/no and (if no `oc`) pasting a token
- **No chatter** — report results, not process
