---
name: trace-setup
description: Set up MLflow production tracing for Claude Code skills. Captures traces (tool calls, LLM interactions, timing, cost) and sends them to the team's shared MLflow instance. Use when asked to enable tracing, set up MLflow, track skill metrics, or opt into production monitoring.
allowed-tools: Bash, Read, AskUserQuestion
---

# Production Tracing Setup

One-command setup for MLflow tracing. After this runs, every Claude Code interaction logs a trace to the team's shared MLflow instance.

## Constants

| Constant | Value |
|----------|-------|
| MLFLOW_URI | `https://rh-ai.apps.rosa.ui-razzmatazz.swih.p3.openshiftapps.com/mlflow` |
| ROSA_API | `https://api.ui-razzmatazz.swih.p3.openshiftapps.com:443` |
| ROSA_CONSOLE | `https://console-openshift-console.apps.rosa.ui-razzmatazz.swih.p3.openshiftapps.com` |
| DEFAULT_EXPERIMENT | `odh-dashboard-skills` |
| DEFAULT_WORKSPACE | `mlflow-agent-eval-harness` |
| VENV_PATH | `${CLAUDE_PLUGIN_ROOT}/.venv` |
| VENV_PYTHON | `${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3` |

## Step 0: Parse Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--status` | false | Check current tracing status and exit |
| `--remove` | false | Disable tracing and exit |
| `--tracking-uri <uri>` | `MLFLOW_URI` | Override MLflow server |
| `--experiment <name>` | `DEFAULT_EXPERIMENT` | MLflow experiment |
| `--workspace <name>` | `DEFAULT_WORKSPACE` | MLflow workspace |

## Step 1: Handle --status

Run the status check and report results. Exit after.

```bash
"${VENV_PYTHON}" "${CLAUDE_PLUGIN_ROOT}/scripts/configure_tracing.py" status
```

If not configured, suggest running `/trace-setup`. If token expired, suggest re-running `/trace-setup` to refresh.

## Step 2: Handle --remove

```bash
"${VENV_PYTHON}" "${CLAUDE_PLUGIN_ROOT}/scripts/configure_tracing.py" remove
```

Tell the user tracing is disabled. Restart Claude Code to take effect. Exit.

## Step 3: Present the plan and confirm

**Do NOT start doing things yet.** First, present exactly what will happen:

> **MLflow Tracing Setup**
>
> This will:
> 1. Ensure MLflow is installed in the plugin's virtual environment
> 2. Authenticate to the ROSA cluster (opens browser for SSO — your current `oc` context is NOT affected)
> 3. Test the MLflow connection
> 4. Save tracing config locally (never committed)
>
> After setup, restart Claude Code and all interactions will be traced to:
> `MLFLOW_URI` (experiment: `DEFAULT_EXPERIMENT`, workspace: `DEFAULT_WORKSPACE`)
>
> **Proceed?**

Use AskUserQuestion with Yes/No. If No, exit immediately.

## Step 4: Install MLflow (automatic)

Check if the plugin venv has mlflow. If not, install it silently. Do NOT ask the user about Python environments — always use the plugin's own venv.

```bash
"${VENV_PYTHON}" -c "import mlflow; print(f'mlflow {mlflow.__version__}')" 2>/dev/null
```

If missing or venv doesn't exist:

```bash
python3 -m venv "${CLAUDE_PLUGIN_ROOT}/.venv"
"${VENV_PYTHON}" -m pip install -q "mlflow[genai]>=3.5"
```

Report: "Installed mlflow X.Y.Z" or "MLflow X.Y.Z already installed". Do not stop or ask questions.

## Step 5: Authenticate to ROSA (automatic)

Get an OpenShift bearer token using a throwaway kubeconfig. The user's current `oc` context is untouched.

Check if `oc` is available:

```bash
which oc 2>/dev/null && echo "OC_AVAILABLE" || echo "OC_MISSING"
```

### Path A: oc available

Run the login directly — it opens the browser automatically:

```bash
TMPKUBE=$(mktemp) && KUBECONFIG=$TMPKUBE oc login --web https://api.ui-razzmatazz.swih.p3.openshiftapps.com:443 2>&1
```

Then extract the token:

```bash
KUBECONFIG=$TMPKUBE oc whoami --show-token
```

**Important:** Both commands must use the SAME temp file. Create it once with `mktemp`, store the path, and reuse it. Do NOT call `mktemp` twice — the second call creates a different file that has no login state.

Clean up: `rm -f $TMPKUBE`

### Path B: oc not available

Tell the user to get a token manually (this is the only time we ask the user to do something):

> `oc` not found. Get a token from the ROSA console:
> 1. Open: `ROSA_CONSOLE`
> 2. Log in → click your username → **"Copy login command"** → **"Display Token"**
> 3. Paste the API token below

Use AskUserQuestion to collect the token.

## Step 6: Configure and verify

Run the setup script with the token:

```bash
"${VENV_PYTHON}" "${CLAUDE_PLUGIN_ROOT}/scripts/configure_tracing.py" setup \
  --uri <tracking_uri> \
  --token <token> \
  --experiment <experiment> \
  --workspace <workspace>
```

The script tests the connection before saving. If it fails:
- **Authentication failed** — token is bad. Go back to Step 5.
- **Connection failed** — network issue. Check VPN.

## Step 7: Report

On success, report concisely:

> **Tracing enabled.**
> - MLflow: `<uri>` (experiment: `<experiment>`, workspace: `<workspace>`)
> - Config: `~/.claude/odh-claude-tracing/tracing.json`
> - **Restart Claude Code** for hooks to take effect
>
> Token expires in ~24h. Re-run `/trace-setup` to refresh.
> Run `/trace-setup --status` to check, `/trace-setup --remove` to disable.

## Rules

- **Present plan first, then execute** — always show what will happen and get confirmation before doing anything
- **Never ask about Python setup** — always use the plugin's .venv at `${CLAUDE_PLUGIN_ROOT}/.venv`
- **Never switch oc context** — always `KUBECONFIG=$(mktemp)` for ROSA auth, reuse the same tempfile
- **Run everything automatically** — the only user interaction is the initial yes/no confirmation and (if no `oc`) pasting a token
- **Use `${VENV_PYTHON}` for all script calls** — not bare `python3`
- **Include `--workspace` in all configure_tracing.py calls** — the MLflow instance requires workspace context
- **No chatter** — don't explain what each command does while running. Report results, not process.
