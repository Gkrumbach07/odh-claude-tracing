---
name: trace-setup
description: Set up MLflow production tracing for Claude Code skills. Captures traces (tool calls, LLM interactions, timing, cost) and sends them to the team's shared MLflow instance. Use when asked to enable tracing, set up MLflow, track skill metrics, or opt into production monitoring.
allowed-tools: Bash, Read, AskUserQuestion
argument-hint: "[--status | --disable]"
---

# Production Tracing Setup

One-command setup for MLflow tracing. Everything is stored in `settings.local.json` so nothing gets committed. The skill owns setup, status, and disable — it does not use `mlflow autolog claude --status` or `--disable` since those only read `settings.json`.

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
| `--status` | false | Run health checks and exit |
| `--disable` | false | Remove tracing config and exit |
| (no args) | — | Full setup flow |

## Step 1: Handle --status

Read `.claude/settings.local.json` and run these checks:

1. **Config exists** — check `env.MLFLOW_TRACKING_URI`, `env.MLFLOW_TRACKING_TOKEN`, `env.MLFLOW_EXPERIMENT_NAME` are present
2. **Stop hook exists** — check `hooks.Stop` contains an entry with `mlflow autolog claude stop-hook`
3. **SessionStart hook exists** — check `hooks.SessionStart` contains the status echo entry
4. **MLflow reachable** — use the token and workspace to call the MLflow experiments API:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" \
     -X POST \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -H "X-Mlflow-Workspace: $WORKSPACE" \
     -d '{"max_results": 1}' \
     "$MLFLOW_URI/api/2.0/mlflow/experiments/search"
   ```
   - 200 = connected
   - 401/403 = token expired
   - Other = connection issue
5. **Experiment exists** — parse the response to confirm the experiment is accessible

Report a table:

| Check | Status |
|-------|--------|
| Config in settings.local.json | OK / MISSING |
| Stop hook | OK / MISSING |
| SessionStart hook | OK / MISSING |
| MLflow connection | OK / TOKEN EXPIRED / UNREACHABLE |
| Experiment `<name>` | OK / NOT FOUND |

If token is expired, suggest: "Re-run `/trace-setup` to refresh your token."

Exit after reporting.

## Step 2: Handle --disable

Read `.claude/settings.local.json`:

1. Remove all `MLFLOW_*` keys from the `env` block
2. Remove the Stop hook entry containing `mlflow autolog claude stop-hook`
3. Remove the SessionStart hook entry
4. Write the file back (preserving permissions and other config)

Report: "Tracing disabled. Restart Claude Code to take effect."

Exit.

## Step 3: Present the plan and confirm

**Do NOT start doing things yet.** Present what will happen:

> **MLflow Tracing Setup**
>
> This will:
> 1. Ensure `mlflow` is installed (in project `.venv` if needed)
> 2. Authenticate to the ROSA cluster (opens browser for SSO — your current `oc` context is NOT affected)
> 3. Run `mlflow autolog claude` to generate the tracing hook
> 4. Move everything to `.claude/settings.local.json` (never committed)
> 5. Add a SessionStart hook to confirm tracing is active on each session
> 6. Restore `.claude/settings.json` to its original state
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

Store the mlflow path as `MLFLOW_CMD`. Use the **absolute path** for `.venv/bin/mlflow` since hooks run in a bare shell.

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
  -u MLFLOW_URI \
  -n DEFAULT_EXPERIMENT
```

This writes `env` and `hooks.Stop` to `.claude/settings.json`.

### 6c: Move config to settings.local.json

Read `.claude/settings.json` (what mlflow just wrote). Read `.claude/settings.local.json` (existing local config). Merge the mlflow entries into settings.local.json:

1. Copy the entire `hooks.Stop` block from settings.json into settings.local.json
2. Copy the `env` block entries from settings.json into settings.local.json's `env`
3. Add these additional env vars to settings.local.json:
   - `MLFLOW_TRACKING_TOKEN`: `<token from Step 5>`
   - `MLFLOW_WORKSPACE`: `DEFAULT_WORKSPACE`
   - `MLFLOW_ENABLE_WORKSPACES`: `true`
4. If the hook command is bare `mlflow autolog claude stop-hook` but mlflow is only in `.venv/bin/`, replace `mlflow` with the absolute path
5. Add a `SessionStart` hook that checks the MLflow connection and prints the result as context for Claude. Use `statusMessage` for a spinner during execution, and stdout so Claude can relay the result:

```json
"SessionStart": [
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "statusMessage": "Checking MLflow tracing...",
        "command": "curl -sf -X POST -H \"Authorization: Bearer $MLFLOW_TRACKING_TOKEN\" -H \"Content-Type: application/json\" -H \"X-Mlflow-Workspace: $MLFLOW_WORKSPACE\" -d '{\"max_results\":1}' \"$MLFLOW_TRACKING_URI/api/2.0/mlflow/experiments/search\" > /dev/null && echo 'MLflow tracing: connected' || echo 'MLflow tracing: NOT connected'"
      }
    ]
  }
]
```

The stdout from this hook becomes context that Claude sees. Claude should relay the tracing status in a very brief one-line mention at the start of its first response (e.g., "MLflow tracing connected." or "MLflow tracing not connected — run `/trace-setup --status`").

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
- **Own the lifecycle** — `--status` and `--disable` read/write settings.local.json directly, do NOT delegate to `mlflow autolog claude --status/--disable`
- **Present plan first, then execute** — show what will happen, get yes/no, then run
- **Backup and restore settings.json** — snapshot before mlflow writes, restore after moving config
- **Never switch oc context** — always `KUBECONFIG=$(mktemp)`, reuse the same tempfile
- **Use absolute paths in hooks** — the Stop hook runs in a bare shell, `.venv/bin/mlflow` won't resolve without the full path
- **Prefer uv over pip** — faster venv creation and install
- **Run everything automatically** — only interaction is the initial yes/no and (if no `oc`) pasting a token
- **No chatter** — report results, not process
