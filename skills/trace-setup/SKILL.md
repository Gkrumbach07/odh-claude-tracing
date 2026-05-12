---
name: trace-setup
description: Set up MLflow production tracing for Claude Code skills. Captures traces (tool calls, LLM interactions, timing, cost) and sends them to the team's shared MLflow instance. Use when asked to enable tracing, set up MLflow, track skill metrics, or opt into production monitoring.
allowed-tools: Bash, Read, Edit, Write, AskUserQuestion
argument-hint: "[on [skill] | off [skill] | reauth | status | uninstall] [--trigger=always|skill|manual] [--skills=a,b,c]"
---

# Production Tracing Setup

One-command setup for MLflow tracing. Config lives in `settings.local.json` (never committed). Hooks ship with the plugin via `hooks/hooks.json` (auto-registered). Supports live on/off toggling and per-skill triggers.

## Key Discovery

Editing `MLFLOW_CLAUDE_TRACING_ENABLED` in `.claude/settings.local.json` toggles tracing **per-turn in real time** — no restart needed. This enables:
- Live `on`/`off` commands
- Hook-based triggers that auto-enable tracing for specific skills
- Context-based auto-disable when a skill completes

## Architecture

| What | Where | Why |
|------|-------|-----|
| Stop hook (sends traces) | `hooks/hooks.json` (plugin) | Static, auto-registered when plugin is enabled |
| SessionStart hook (health check) | `hooks/hooks.json` (plugin) | Static, auto-registered |
| Env vars (token, URI, etc.) | `.claude/settings.local.json` | Per-user secrets, never committed |
| PreToolUse hooks (per-skill `if` entries) | `.claude/settings.local.json` | Dynamic, user-configured |

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
| (none) | Full install/reconfigure flow |
| `on` | Turn tracing ON immediately (global live toggle) |
| `off` | Turn tracing OFF immediately (global live toggle) |
| `on <skill>` | Add a skill to the traced skills list (adds `if`-filtered PreToolUse hook entry) |
| `off <skill>` | Remove a skill from the traced skills list (removes its `if` entry) |
| `reauth` | Refresh expired ROSA token (skips full install) |
| `status` | Health check and exit |
| `uninstall` | Remove all tracing config |

Install-time options (only during install):

| Option | Default | Description |
|--------|---------|-------------|
| `--trigger=always` | ✓ | Tracing always on — every turn is traced |
| `--trigger=skill` | | Tracing off by default; auto-enables for specific skills via `if`-filtered hooks |
| `--trigger=manual` | | Tracing off by default; use `/trace-setup on` and `/trace-setup off` to control |
| `--skills=a,b,c` | | Shorthand to add multiple skills during install (only with `--trigger=skill`) |

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

Adds an `if`-filtered hook entry so tracing auto-enables when the named skill is invoked. Requires `--trigger=skill` mode.

1. Read `.claude/settings.local.json`
2. If `MLFLOW_TRACKING_URI` is not present in `env`, error: "Tracing not installed. Run `/trace-setup` first."
3. Ensure `MLFLOW_TRACING_TRIGGER` is `"skill"`. If it's `"always"`, warn: "Trigger mode is `always` — all turns are already traced. Switch to `skill` mode first with `/trace-setup --trigger=skill`." and exit. If it's `"manual"`, update it to `"skill"`.
4. Look for `hooks.PreToolUse` array. If it doesn't exist, create it.
5. Find the entry with `"matcher": "Skill"`. If it doesn't exist, create it with an empty `hooks` array.
6. Check if an `if` entry for this skill already exists (e.g., `"if": "Skill(<skill>:*)"`). If so, announce **"Skill `<skill>` is already traced."** and exit.
7. Add a new hook entry inside the matcher's `hooks` array:

   ```json
   {
     "type": "command",
     "if": "Skill(<skill>:*)",
     "command": "sed -i.bak 's/\"MLFLOW_CLAUDE_TRACING_ENABLED\": \"false\"/\"MLFLOW_CLAUDE_TRACING_ENABLED\": \"true\"/' .claude/settings.local.json && rm -f .claude/settings.local.json.bak && echo 'MLflow tracing: ON (<skill> invoked). IMPORTANT: You MUST turn tracing off when this skill fully completes (all follow-ups resolved, final output delivered). Run: sed -i.bak '\"'\"'s/\"MLFLOW_CLAUDE_TRACING_ENABLED\": \"true\"/\"MLFLOW_CLAUDE_TRACING_ENABLED\": \"false\"/'\"'\"' .claude/settings.local.json && rm -f .claude/settings.local.json.bak — then announce: MLflow tracing: OFF'"
   }
   ```

8. Write the file back.
9. Announce: **"Skill `<skill>` added to traced skills. Tracing will auto-enable when `/<skill>` is invoked."**

**Note on the hook command**: The echo output becomes context that Claude sees. It includes an instruction telling Claude to turn tracing back off when the skill work is fully complete. Claude judges when the skill is done (even across multi-turn follow-ups) and runs the sed command to disable tracing, then announces "MLflow tracing: OFF".

Exit after.

## Step 4: Handle `off <skill>` (remove skill from traced list)

Removes the `if`-filtered hook entry for the named skill.

1. Read `.claude/settings.local.json`
2. If `MLFLOW_TRACKING_URI` is not present in `env`, error: "Tracing not installed. Run `/trace-setup` first."
3. Find `hooks.PreToolUse` → entry with `"matcher": "Skill"` → hook with `"if": "Skill(<skill>:*)"`.
4. If not found, announce **"Skill `<skill>` is not in the traced skills list."** and exit.
5. Remove that hook entry from the array.
6. If the matcher's `hooks` array is now empty, remove the entire matcher entry.
7. If the `PreToolUse` array is now empty, remove it entirely.
8. Write the file back.
9. Announce: **"Skill `<skill>` removed from traced skills."**

Exit after.

---

## Step 5: Handle `reauth`

Quick token refresh — skips mlflow install, hook setup, and reconfiguration. Only re-authenticates to ROSA and updates the token.

1. Read `.claude/settings.local.json`
2. If `MLFLOW_TRACKING_URI` is not present in `env`, error: "Tracing not installed. Run `/trace-setup` first."
3. Authenticate to ROSA using the same flow as Step 10 (oc login with throwaway kubeconfig, or manual token paste if oc is unavailable). **No confirmation needed** — proceed directly.
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
   - If not 200: announce **"Token refreshed but connection failed (HTTP <code>). Check `/trace-setup --status`."**

Exit after.

---

## Step 6: Handle `status`

Read `.claude/settings.local.json` and run these checks:

1. **Config exists** — check `env.MLFLOW_TRACKING_URI`, `env.MLFLOW_TRACKING_TOKEN`, `env.MLFLOW_EXPERIMENT_NAME` are present
2. **Tracing state** — read `env.MLFLOW_CLAUDE_TRACING_ENABLED` (true/false)
3. **Trigger mode** — read `env.MLFLOW_TRACING_TRIGGER` (always/skill/manual)
4. **Traced skills** — if trigger=skill, list all skills that have `if` entries in the PreToolUse Skill matcher (extract skill names from `"if": "Skill(<name>:*)"` patterns)
5. **MLflow reachable** — use the token and workspace to call the MLflow experiments API:
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
6. **Experiment exists** — parse the response to confirm the experiment is accessible

Report a table:

| Check | Status |
|-------|--------|
| Config in settings.local.json | OK / MISSING |
| Tracing state | ON / OFF |
| Trigger mode | always / skill / manual |
| Traced skills | preflight, jira-triage / (none) / N/A |
| MLflow connection | OK / TOKEN EXPIRED / UNREACHABLE |
| Experiment `<name>` | OK / NOT FOUND |

If token is expired, suggest: "Run `/trace-setup reauth` to refresh your token."

Exit after reporting.

---

## Step 7: Handle `uninstall`

Read `.claude/settings.local.json`:

1. Remove all `MLFLOW_*` keys from the `env` block
2. Remove any PreToolUse hook entries with matcher `Skill` that contain `MLFLOW_CLAUDE_TRACING_ENABLED`
3. If any hook array becomes empty after removal, remove the array entirely
4. If the `hooks` object becomes empty, remove it entirely
5. Write the file back (preserving other config)

Report: "Tracing removed. Plugin hooks (Stop/SessionStart) are still registered but will no-op without the env vars."

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
>
> **Trigger mode: `<trigger>`**
> - `always` — every turn is traced
> - `skill` — tracing auto-enables for specific skills; use `/trace-setup on <skill>` to add
> - `manual` — use `/trace-setup on` and `/trace-setup off` to control
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

Store the resolved absolute path as `MLFLOW_CMD` (e.g., `/opt/homebrew/bin/mlflow` or `/path/to/project/.venv/bin/mlflow`). The plugin's `hooks/hooks.json` references `mlflow` by name — if mlflow is only in a local `.venv`, the user may need to ensure it's on PATH or symlinked.

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

## Step 11: Write env vars to settings.local.json

Read `.claude/settings.local.json` (or create it if it doesn't exist). Merge these env vars into the `env` block:

```json
{
  "env": {
    "MLFLOW_CLAUDE_TRACING_ENABLED": "<true if always, false if skill/manual>",
    "MLFLOW_TRACKING_URI": "https://rh-ai.apps.rosa.ui-razzmatazz.swih.p3.openshiftapps.com/mlflow",
    "MLFLOW_EXPERIMENT_NAME": "odh-dashboard-skills",
    "MLFLOW_TRACKING_TOKEN": "<token from Step 10>",
    "MLFLOW_WORKSPACE": "mlflow-agent-eval-harness",
    "MLFLOW_ENABLE_WORKSPACES": "true",
    "MLFLOW_TRACING_TRIGGER": "<trigger mode>"
  }
}
```

If `--trigger=skill` and `--skills=a,b,c` was provided, also add per-skill PreToolUse hook entries following the same pattern as Step 3 (`on <skill>`).

Preserve all existing config in settings.local.json (permissions, other env vars, other hooks).

## Step 12: Report

> **Tracing installed.**
> - MLflow: `<uri>` (experiment: `<experiment>`, workspace: `<workspace>`)
> - Trigger: `<trigger mode>`
> - Traced skills: `<list>` (or "none — use `/trace-setup on <skill>` to add")
> - Config: `.claude/settings.local.json` (not committed)
>
> Token expires in ~24h. Run `/trace-setup reauth` to refresh.
>
> **Commands:**
> - `/trace-setup on` — turn tracing on now (global)
> - `/trace-setup off` — turn tracing off now (global)
> - `/trace-setup on <skill>` — add a skill to auto-trace list
> - `/trace-setup off <skill>` — remove a skill from auto-trace list
> - `/trace-setup reauth` — refresh expired token
> - `/trace-setup --status` — check health and list traced skills
> - `/trace-setup uninstall` — remove tracing

## How per-skill tracing works

1. User runs `/trace-setup --trigger=skill` then `/trace-setup on preflight`
2. This adds a `PreToolUse` hook in settings.local.json with `"matcher": "Skill"` and `"if": "Skill(preflight:*)"`
3. When the user runs `/preflight`, the hook fires:
   - Flips `MLFLOW_CLAUDE_TRACING_ENABLED` from `false` to `true` via sed
   - Echoes a message back to Claude: "MLflow tracing: ON (preflight invoked). IMPORTANT: You MUST turn tracing off when this skill fully completes..."
4. Claude sees this instruction as context and follows it
5. The skill runs — possibly across multiple turns with follow-up questions
6. When Claude determines the skill work is fully complete, it runs the sed command to flip tracing back to `false` and announces "MLflow tracing: OFF"
7. As a safety net, the plugin's Stop hook also resets tracing to `false` on session exit (for non-always modes)

## Rules

- **Env vars in settings.local.json** — never committed, per-user secrets
- **Static hooks in hooks/hooks.json** — ship with the plugin, auto-registered
- **Dynamic hooks (PreToolUse per-skill) in settings.local.json** — user-configured
- **`on`/`off` (global) are instant** — no confirmation, no chatter, just edit and announce
- **`on`/`off` with skill name** modifies the PreToolUse hook array in settings.local.json
- **Present plan first for install** — show what will happen, get yes/no, then run
- **Never switch oc context** — always `KUBECONFIG=$(mktemp)`, reuse the same tempfile
- **Always announce state changes** — when tracing turns on or off, say so clearly
- **Per-skill hooks use `if` field** — `"if": "Skill(<name>:*)"` filters on the skill name argument
- **Auto-disable via context** — the hook echo instructs Claude to turn tracing off when the skill completes
- **No chatter** — report results, not process
