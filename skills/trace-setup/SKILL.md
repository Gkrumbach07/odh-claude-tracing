---
name: trace-setup
description: Set up MLflow production tracing for Claude Code skills. Captures traces (tool calls, LLM interactions, timing, cost) and sends them to the team's shared MLflow instance. Use when asked to enable tracing, set up MLflow, track skill metrics, or opt into production monitoring.
allowed-tools: Bash, Read, Edit, Write, AskUserQuestion
argument-hint: "[on [skill] | off [skill] | reauth | status | uninstall] [--skills=a,b,c]"
---

# Production Tracing Setup

One-command setup for MLflow tracing. Supports live on/off toggling and per-skill auto-tracing.

## Key Discoveries

1. Editing `MLFLOW_CLAUDE_TRACING_ENABLED` in `.claude/settings.local.json` toggles tracing **per-turn in real time** — but only when Claude uses the Edit tool (external `sed` edits are not detected).
2. Skills invoked via `/skillname` are **prompt expansions**, not tool calls — use `UserPromptExpansion` hooks, not `PreToolUse`.
3. `UserPromptExpansion` stdout is invisible to Claude — must use JSON with `hookSpecificOutput.additionalContext`.
4. `SessionStart` hooks only work from `.claude/settings.json`, not settings.local.json. Use `systemMessage` in JSON output.

## Architecture

Config is split across two files:

| What | Where | Why |
|------|-------|-----|
| SessionStart hook (health check) | `.claude/settings.json` | SessionStart only fires from settings.json |
| Stop hook (sends traces) | `.claude/settings.json` | Same reason — lifecycle hooks need settings.json |
| Env vars (token, URI, etc.) | `.claude/settings.local.json` | Per-user secrets, never committed |
| UserPromptExpansion hooks (per-skill) | `.claude/settings.local.json` | Dynamic, user-configured, never committed |

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

| Argument | Description |
|----------|-------------|
| (none) | Full install — tracing always on |
| `--skills=a,b,c` | Install with tracing off by default, auto-on for listed skills |
| `on` | Turn tracing ON immediately (global live toggle) |
| `off` | Turn tracing OFF immediately (global live toggle) |
| `on <skill>` | Add a skill to the auto-trace list |
| `off <skill>` | Remove a skill from the auto-trace list |
| `reauth` | Refresh expired ROSA token (skips full install) |
| `status` | Health check and exit |
| `uninstall` | Remove all tracing config |

**How install mode is determined:**
- `/trace-setup` → tracing always on (every turn traced)
- `/trace-setup --skills=preflight,jira-triage` → tracing off by default, auto-enables for listed skills

---

## Step 1: Handle `on` (no skill name — global toggle)

Quick operation — no confirmation needed.

1. Read `.claude/settings.local.json`
2. If `MLFLOW_TRACKING_URI` is not present in `env`, error: "Tracing not installed. Run `/trace-setup` first."
3. Check the current value of `MLFLOW_CLAUDE_TRACING_ENABLED`
   - If already `"true"`, announce **"MLflow tracing: already ON"** and exit
4. Edit the file: change `"MLFLOW_CLAUDE_TRACING_ENABLED": "false"` to `"MLFLOW_CLAUDE_TRACING_ENABLED": "true"`
5. Announce: **"MLflow tracing: ON"**

Exit immediately after.

## Step 2: Handle `off` (no skill name — global toggle)

Quick operation — no confirmation needed.

1. Read `.claude/settings.local.json`
2. If `MLFLOW_TRACKING_URI` is not present in `env`, error: "Tracing not installed. Run `/trace-setup` first."
3. Check the current value of `MLFLOW_CLAUDE_TRACING_ENABLED`
   - If already `"false"`, announce **"MLflow tracing: already OFF"** and exit
4. Edit the file: change `"MLFLOW_CLAUDE_TRACING_ENABLED": "true"` to `"MLFLOW_CLAUDE_TRACING_ENABLED": "false"`
5. Announce: **"MLflow tracing: OFF"**

Exit immediately after.

---

## Step 3: Handle `on <skill>` (add skill to traced list)

Adds a `UserPromptExpansion` hook entry so tracing auto-enables when the named skill is invoked via `/skillname`.

1. Read `.claude/settings.local.json`
2. If `MLFLOW_TRACKING_URI` is not present in `env`, error: "Tracing not installed. Run `/trace-setup` first."
3. If `MLFLOW_CLAUDE_TRACING_ENABLED` is `"true"` and no skills are currently in the traced list, warn: "Tracing is always on — all turns are already traced. Run `/trace-setup off` first if you want per-skill tracing." and exit.
4. Look for `hooks.UserPromptExpansion` array. If it doesn't exist, create it.
5. Check if an entry with `"matcher": "<skill>"` already exists. If so, announce **"Skill `<skill>` is already traced."** and exit.
6. Add a new entry to the `UserPromptExpansion` array:

   ```json
   {
     "matcher": "<skill>",
     "hooks": [
       {
         "type": "command",
         "command": "printf '{\"hookSpecificOutput\":{\"hookEventName\":\"UserPromptExpansion\",\"additionalContext\":\"TRACING INSTRUCTION: You MUST immediately use the Edit tool to change MLFLOW_CLAUDE_TRACING_ENABLED from false to true in .claude/settings.local.json, then announce: MLflow tracing: ON. When this skill fully completes (all follow-ups resolved, final output delivered), use the Edit tool to change it back to false and announce: MLflow tracing: OFF.\"}}'"
       }
     ]
   }
   ```

7. Write the file back.
8. Announce: **"Skill `<skill>` added to traced skills. Tracing will auto-enable when `/<skill>` is invoked."**

**Important: Why JSON output, not plain text.** `UserPromptExpansion` hooks ignore plain stdout — only JSON with `additionalContext` in `hookSpecificOutput` is visible to Claude. Claude then uses the Edit tool to flip the setting, which triggers Claude Code to re-read settings.local.json.

Exit after.

## Step 4: Handle `off <skill>` (remove skill from traced list)

Removes the `UserPromptExpansion` hook entry for the named skill.

1. Read `.claude/settings.local.json`
2. If `MLFLOW_TRACKING_URI` is not present in `env`, error: "Tracing not installed. Run `/trace-setup` first."
3. Find `hooks.UserPromptExpansion` → entry with `"matcher": "<skill>"`.
4. If not found, announce **"Skill `<skill>` is not in the traced skills list."** and exit.
5. Remove that entry from the array.
6. If the `UserPromptExpansion` array is now empty, remove it entirely.
7. Write the file back.
8. Announce: **"Skill `<skill>` removed from traced skills."**

Exit after.

---

## Step 5: Handle `reauth`

Quick token refresh — skips mlflow install, hook setup, and reconfiguration. Only re-authenticates to ROSA and updates the token.

1. Read `.claude/settings.local.json`
2. If `MLFLOW_TRACKING_URI` is not present in `env`, error: "Tracing not installed. Run `/trace-setup` first."
3. Authenticate to ROSA (oc login with throwaway kubeconfig, or manual token paste if oc is unavailable — same auth flow as the install). **No confirmation needed** — proceed directly.
4. Update `MLFLOW_TRACKING_TOKEN` in the `env` block of `.claude/settings.local.json` with the new token.
5. Verify the new token works:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" \
     -X POST \
     -H "Authorization: Bearer $NEW_TOKEN" \
     -H "Content-Type: application/json" \
     -H "X-Mlflow-Workspace: $WORKSPACE" \
     -d '{"max_results": 1}' \
     "$MLFLOW_URI/api/2.0/mlflow/experiments/search"
   ```
   - If 200: announce **"Token refreshed. MLflow tracing: connected."**
   - If not 200: announce **"Token refreshed but connection failed (HTTP <code>). Check `/trace-setup status`."**

Exit after.

---

## Step 6: Handle `status`

Read both `.claude/settings.local.json` and `.claude/settings.json` and run these checks:

1. **Config exists** — check `env.MLFLOW_TRACKING_URI`, `env.MLFLOW_TRACKING_TOKEN`, `env.MLFLOW_EXPERIMENT_NAME` are present in settings.local.json
2. **Tracing state** — read `env.MLFLOW_CLAUDE_TRACING_ENABLED` (true/false)
3. **Traced skills** — list all skills that have entries in the `UserPromptExpansion` array in settings.local.json (extract skill names from `"matcher"` values)
4. **Stop hook** — check settings.json `hooks.Stop` contains `mlflow autolog claude stop-hook`
5. **SessionStart hook** — check settings.json `hooks.SessionStart` contains the MLflow check
6. **MLflow reachable** — use the token and workspace to call the MLflow experiments API:
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
7. **Experiment exists** — parse the response to confirm the experiment is accessible

Report a table:

| Check | Status |
|-------|--------|
| Config in settings.local.json | OK / MISSING |
| Tracing state | ON / OFF |
| Traced skills | preflight, jira-triage / (none) |
| Stop hook (settings.json) | OK / MISSING |
| SessionStart hook (settings.json) | OK / MISSING |
| MLflow connection | OK / TOKEN EXPIRED / UNREACHABLE |
| Experiment `<name>` | OK / NOT FOUND |

If token is expired, suggest: "Run `/trace-setup reauth` to refresh your token."

Exit after reporting.

---

## Step 7: Handle `uninstall`

Remove config from **both** files:

**From `.claude/settings.local.json`:**
1. Remove all `MLFLOW_*` keys from the `env` block
2. Remove any `UserPromptExpansion` hook entries that contain `MLFLOW_CLAUDE_TRACING_ENABLED` in their `additionalContext`
3. If any hook array becomes empty after removal, remove the array entirely
4. If the `hooks` object becomes empty, remove it entirely

**From `.claude/settings.json`:**
5. Remove the Stop hook entry containing `mlflow autolog claude stop-hook`
6. Remove the SessionStart hook entry containing `MLflow Tracing`
7. If any hook array becomes empty after removal, remove the array entirely
8. If the `hooks` object becomes empty, remove it entirely
9. If settings.json is now empty (`{}`), delete the file

Write both files back (preserving other config).

Report: "Tracing removed."

Exit.

---

## Step 8: Install flow — present plan and confirm

**Do NOT start doing things yet.** Present what will happen:

> **MLflow Tracing Setup**
>
> This will:
> 1. Ensure `mlflow` is installed (needed for the stop-hook that sends traces)
> 2. Authenticate to the ROSA cluster (opens browser for SSO — your current `oc` context is NOT affected)
> 3. Write env vars to `.claude/settings.local.json` (never committed)
> 4. Write lifecycle hooks to `.claude/settings.json`
>
> **Mode:** `<always on>` or `<off by default, auto-on for: skill1, skill2>`
>
> **Prerequisites:** Python >= 3.11
>
> After setup, traces go to:
> `MLFLOW_URI` (experiment: `DEFAULT_EXPERIMENT`)
>
> **Proceed?**

Use AskUserQuestion with Yes/No. If No, exit.

## Step 9: Ensure mlflow is installed

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

Store the resolved absolute path as `MLFLOW_CMD` (e.g., `/opt/homebrew/bin/mlflow` or `/path/to/project/.venv/bin/mlflow`). If mlflow is only in a local `.venv`, the user may need to ensure it's on PATH or symlinked so the Stop hook can find it.

## Step 10: Authenticate to ROSA

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

## Step 11: Write config

### To `.claude/settings.local.json`

Read the file (or create it if it doesn't exist). Merge these env vars into the `env` block:

```json
{
  "env": {
    "MLFLOW_CLAUDE_TRACING_ENABLED": "<true if no --skills, false if --skills provided>",
    "MLFLOW_TRACKING_URI": "https://rh-ai.apps.rosa.ui-razzmatazz.swih.p3.openshiftapps.com/mlflow",
    "MLFLOW_EXPERIMENT_NAME": "odh-dashboard-skills",
    "MLFLOW_TRACKING_TOKEN": "<token from Step 10>",
    "MLFLOW_WORKSPACE": "mlflow-agent-eval-harness",
    "MLFLOW_ENABLE_WORKSPACES": "true"
  }
}
```

If `--skills=a,b,c` was provided, also add `UserPromptExpansion` hook entries following the same pattern as Step 3 (`on <skill>`).

Preserve all existing config (permissions, other env vars, other hooks).

### To `.claude/settings.json`

Read the file (or create it if it doesn't exist). Add these hooks (append to existing hook arrays, do not replace other entries):

**Stop hook** — sends traces to MLflow on session exit:

```json
"Stop": [
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "command": "which mlflow >/dev/null 2>&1 && mlflow autolog claude stop-hook || true"
      }
    ]
  }
]
```

**SessionStart hook** — reports tracing status on session start:

```json
"SessionStart": [
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "command": "if [ -z \"$MLFLOW_TRACKING_URI\" ]; then exit 0; fi; if curl -sf -X POST -H \"Authorization: Bearer $MLFLOW_TRACKING_TOKEN\" -H \"Content-Type: application/json\" -H \"X-Mlflow-Workspace: $MLFLOW_WORKSPACE\" -d '{\"max_results\":1}' \"$MLFLOW_TRACKING_URI/api/2.0/mlflow/experiments/search\" > /dev/null 2>&1; then if [ \"$MLFLOW_CLAUDE_TRACING_ENABLED\" = \"true\" ]; then echo '{\"systemMessage\":\"MLflow Tracing ON\"}'; else echo '{\"systemMessage\":\"MLflow Tracing OFF\"}'; fi; else echo '{\"systemMessage\":\"MLflow Tracing DISCONNECTED (run /trace-setup reauth)\"}'; fi"
      }
    ]
  }
]
```

Preserve all existing config in settings.json.

## Step 12: Report

> **Tracing installed.**
> - MLflow: `<uri>` (experiment: `<experiment>`, workspace: `<workspace>`)
> - Mode: `<always on>` or `<off by default, auto-on for: skill1, skill2>`
> - Config: `.claude/settings.local.json` (env vars) + `.claude/settings.json` (hooks)
>
> Token expires in ~24h. Run `/trace-setup reauth` to refresh.
>
> **Commands:**
> - `/trace-setup on` — turn tracing on now
> - `/trace-setup off` — turn tracing off now
> - `/trace-setup on <skill>` — add a skill to auto-trace list
> - `/trace-setup off <skill>` — remove a skill from auto-trace list
> - `/trace-setup reauth` — refresh expired token
> - `/trace-setup status` — check health and list traced skills
> - `/trace-setup uninstall` — remove tracing

## How per-skill tracing works

1. User runs `/trace-setup --skills=preflight` (or `/trace-setup` then `/trace-setup on preflight`)
2. This adds a `UserPromptExpansion` hook in settings.local.json with `"matcher": "preflight"`
3. When the user types `/preflight`, the hook fires and outputs JSON with `additionalContext`
4. Claude sees the tracing instruction injected into the prompt context
5. Claude uses the Edit tool to change `MLFLOW_CLAUDE_TRACING_ENABLED` from `false` to `true` — this triggers Claude Code to re-read settings, enabling tracing
6. Claude announces "MLflow tracing: ON" and proceeds with the skill
7. The skill runs — possibly across multiple turns with follow-up questions
8. When Claude determines the skill work is fully complete, it uses Edit to change ENABLED back to `false` and announces "MLflow tracing: OFF"
9. The Stop hook sends traces on session exit

## Rules

- **Env vars + UserPromptExpansion in settings.local.json** — never committed
- **SessionStart + Stop in settings.json** — lifecycle hooks only work from settings.json
- **Use UserPromptExpansion, NOT PreToolUse** — `/skillname` is a prompt expansion, not a tool call
- **UserPromptExpansion needs JSON output** — use `hookSpecificOutput.additionalContext`
- **SessionStart uses systemMessage** — `echo '{"systemMessage":"..."}'`
- **Claude must use Edit tool to flip settings** — external `sed` edits are not detected
- **Each skill gets its own matcher entry** — `"matcher": "<skill-name>"`
- **`on`/`off` (global) are instant** — no confirmation, no chatter, just edit and announce
- **Present plan first for install** — show what will happen, get yes/no, then run
- **Never switch oc context** — always `KUBECONFIG=$(mktemp)`, reuse the same tempfile
- **Always announce state changes** — when tracing turns on or off, say so clearly
- **Auto-disable via context** — the hook injects an instruction via additionalContext telling Claude to turn tracing off when the skill completes
- **No chatter** — report results, not process
