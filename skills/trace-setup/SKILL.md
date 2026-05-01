---
name: trace-setup
description: Set up MLflow production tracing for Claude Code skills. Captures traces (tool calls, LLM interactions, timing, cost) and sends them to the team's shared MLflow instance. Use when asked to enable tracing, set up MLflow, track skill metrics, or opt into production monitoring.
allowed-tools: Bash, Read, AskUserQuestion
---

# Production Tracing Setup

One-command setup for MLflow tracing using `mlflow autolog claude`. After this runs, every Claude Code interaction logs a trace to the team's shared MLflow instance.

## Constants

| Constant | Value |
|----------|-------|
| MLFLOW_URI | `https://rh-ai.apps.rosa.ui-razzmatazz.swih.p3.openshiftapps.com/mlflow` |
| ROSA_API | `https://api.ui-razzmatazz.swih.p3.openshiftapps.com:443` |
| ROSA_CONSOLE | `https://console-openshift-console.apps.rosa.ui-razzmatazz.swih.p3.openshiftapps.com` |
| DEFAULT_EXPERIMENT | `odh-dashboard-skills` |

## Step 0: Parse Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--status` | false | Check current tracing status and exit |
| `--disable` | false | Disable tracing and exit |
| `--tracking-uri <uri>` | `MLFLOW_URI` | Override MLflow server |
| `--experiment <name>` | `DEFAULT_EXPERIMENT` | MLflow experiment |

## Step 1: Handle --status

```bash
mlflow autolog claude --status
```

Report the output. If mlflow is not found, check for it in a `.venv`:

```bash
.venv/bin/mlflow autolog claude --status 2>/dev/null || pip install "mlflow[genai]>=3.5"
```

Exit after reporting.

## Step 2: Handle --disable

```bash
mlflow autolog claude --disable
```

Tell the user tracing is disabled. Restart Claude Code to take effect. Exit.

## Step 3: Present the plan and confirm

**Do NOT start doing things yet.** Present what will happen:

> **MLflow Tracing Setup**
>
> This will:
> 1. Ensure `mlflow` is installed
> 2. Authenticate to the ROSA cluster (opens browser for SSO — your current `oc` context is NOT affected)
> 3. Run `mlflow autolog claude` to configure the Stop hook
> 4. Add MLflow env vars (tracking URI, token, workspace) to `.claude/settings.json`
>
> After setup, restart Claude Code and all interactions will be traced to:
> `MLFLOW_URI` (experiment: `DEFAULT_EXPERIMENT`)
>
> **Proceed?**

Use AskUserQuestion with Yes/No. If No, exit.

## Step 4: Ensure mlflow is installed

```bash
which mlflow 2>/dev/null || .venv/bin/mlflow --version 2>/dev/null
```

If not found anywhere, create a venv and install:

```bash
python3 -m venv .venv
.venv/bin/pip install -q "mlflow[genai]>=3.5"
```

Determine the mlflow binary path for subsequent commands. Store it (e.g., `MLFLOW_CMD=mlflow` or `MLFLOW_CMD=.venv/bin/mlflow`).

## Step 5: Authenticate to ROSA

Get an OpenShift bearer token using a throwaway kubeconfig.

Check if `oc` is available:

```bash
which oc 2>/dev/null && echo "OC_AVAILABLE" || echo "OC_MISSING"
```

### Path A: oc available

Run the login directly — create a temp kubeconfig, login, extract token, clean up. **Use the same temp file for both commands.**

```bash
TMPKUBE=$(mktemp)
KUBECONFIG=$TMPKUBE oc login --web https://api.ui-razzmatazz.swih.p3.openshiftapps.com:443
TOKEN=$(KUBECONFIG=$TMPKUBE oc whoami --show-token)
rm -f $TMPKUBE
```

### Path B: oc not available

Ask the user to get a token from the ROSA console:

> `oc` not found. Get a token from the ROSA console:
> 1. Open: `ROSA_CONSOLE`
> 2. Log in → click your username → **"Copy login command"** → **"Display Token"**
> 3. Paste the API token below

Use AskUserQuestion to collect the token.

## Step 6: Run mlflow autolog claude

```bash
$MLFLOW_CMD autolog claude \
  -u <tracking_uri> \
  -n <experiment>
```

Then add the auth env vars to `.claude/settings.json` — the `env` block. Read the current settings.json, merge in:

```json
{
  "env": {
    "MLFLOW_TRACKING_TOKEN": "<token>",
    "MLFLOW_WORKSPACE": "mlflow-agent-eval-harness",
    "MLFLOW_ENABLE_WORKSPACES": "true"
  }
}
```

**Important:** `mlflow autolog claude` sets `MLFLOW_TRACKING_URI`, `MLFLOW_EXPERIMENT_NAME`, and `MLFLOW_CLAUDE_TRACING_ENABLED` in the env block. You only need to add `MLFLOW_TRACKING_TOKEN`, `MLFLOW_WORKSPACE`, and `MLFLOW_ENABLE_WORKSPACES`.

Also check: if the hook command is bare `mlflow autolog claude stop-hook` but mlflow isn't on the system PATH, replace it with the full path (e.g., `.venv/bin/mlflow autolog claude stop-hook`).

## Step 7: Report

> **Tracing enabled.**
> - MLflow: `<uri>` (experiment: `<experiment>`)
> - **Restart Claude Code** for the hook to take effect
>
> Token expires in ~24h. Re-run `/trace-setup` to refresh.
> Run `/trace-setup --status` to check, `/trace-setup --disable` to turn off.

## Rules

- **Present plan first, then execute** — show what will happen, get yes/no, then run everything
- **Use `mlflow autolog claude`** — don't write custom hooks or scripts
- **Never switch oc context** — always `KUBECONFIG=$(mktemp)` for ROSA auth, reuse the same tempfile
- **Run everything automatically** — only interaction is the initial yes/no and (if no `oc`) pasting a token
- **No chatter** — report results, not process
