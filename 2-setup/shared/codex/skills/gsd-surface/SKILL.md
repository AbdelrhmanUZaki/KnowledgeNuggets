---
name: "gsd-surface"
description: "Toggle which skills are surfaced — apply a profile, list, or disable a cluster without reinstall"
metadata:
  short-description: "Toggle which skills are surfaced — apply a profile, list, or disable a cluster without reinstall"
---

<codex_skill_adapter>
## A. Skill Invocation
- This skill is invoked by mentioning `$gsd-surface`.
- Treat all user text after `$gsd-surface` as `{{GSD_ARGS}}`.
- If no arguments are present, treat `{{GSD_ARGS}}` as empty.

## B. AskUserQuestion → request_user_input Mapping
GSD workflows use `AskUserQuestion` (Claude Code syntax). Translate to Codex `request_user_input`:

Parameter mapping:
- `header` → `header`
- `question` → `question`
- Options formatted as `"Label" — description` → `{label: "Label", description: "description"}`
- Generate `id` from header: lowercase, replace spaces with underscores

Batched calls:
- `AskUserQuestion([q1, q2])` → single `request_user_input` with multiple entries in `questions[]`

Multi-select workaround:
- Codex has no `multiSelect`. Use sequential single-selects, or present a numbered freeform list asking the user to enter comma-separated numbers.

Execute mode fallback:
- When `request_user_input` is rejected or unavailable, you MUST stop and present the questions as a plain-text numbered list, then wait for the user's reply. Do NOT pick a default and continue (#3018).
- You may only proceed without a user answer when one of these is true:
  (a) the invocation included an explicit non-interactive flag (`--auto` or `--all`),
  (b) the user has explicitly approved a specific default for this question, or
  (c) the workflow's documented contract says defaults are safe (e.g. autonomous lifecycle paths).
- Do NOT write workflow artifacts (CONTEXT.md, DISCUSSION-LOG.md, PLAN.md, checkpoint files) until the user has answered the plain-text questions or one of (a)-(c) above applies. Surfacing the questions and waiting is the correct response — silently defaulting and writing artifacts is the #3018 failure mode.

## C. Task() → spawn_agent Mapping
GSD workflows use `Task(...)` (Claude Code syntax). Translate to Codex collaboration tools:

Direct mapping:
- `Task(subagent_type="X", prompt="Y")` → `spawn_agent(agent_type="X", message="Y")`
- `Task(model="...")` → omit. `spawn_agent` has no inline `model` parameter;
  GSD embeds the resolved per-agent model directly into each agent's `.toml`
  at install time so `model_overrides` from `.planning/config.json` and
  `~/.gsd/defaults.json` are honored automatically by Codex's agent router.
- Resolved `reasoning_effort="low|medium|high|xhigh"` (`xhigh` is a GSD/Codex tier, not a generic runtime enum) → pass `reasoning_effort`
  to `spawn_agent` when the runtime/tool supports it. Omit missing, empty,
  inherited, or unsupported values; do not invent one-off effort literals in
  workflow prose.
- `fork_context: false` by default — GSD agents load their own context via `<files_to_read>` blocks
- `Task(isolation="worktree")` / `Agent(isolation="worktree")` → no direct Codex mapping.
  Codex `spawn_agent` does not create or bind a git worktree automatically.
  Workflows that require this isolation must fail closed or use an explicit
  manual worktree protocol before spawning (#3360).

Spawn restriction:
- Codex restricts `spawn_agent` to cases where the user has explicitly
  requested sub-agents. When automatic spawning is not permitted, do the
  work inline in the current agent rather than attempting to force a spawn.

Parallel fan-out:
- Spawn multiple agents → collect agent IDs → `wait(ids)` for all to complete

Result parsing:
- Look for structured markers in agent output: `CHECKPOINT`, `PLAN COMPLETE`, `SUMMARY`, etc.
- `close_agent(id)` after collecting results from each agent
</codex_skill_adapter>

<objective>
Manage the runtime skill surface without reinstall. Reads/writes `$HOME/.codex/skills/.gsd-surface.json`
(sibling to `.gsd-profile`) and re-stages the active commands/gsd directory in place.

Sub-commands: list · status · profile · disable · enable · reset
</objective>

## Sub-command routing

Parse the first token of {{GSD_ARGS}}:

| Token | Action |
|---|---|
| `list` | Show enabled + disabled clusters and skills |
| `status` | Alias for `list` plus token cost summary |
| `profile <name>` | Write `baseProfile` and re-stage |
| `profile <n1>,<n2>` | Composed profiles (comma-separated, no spaces) |
| `disable <cluster>` | Add cluster to `disabledClusters`, re-stage |
| `enable <cluster>` | Remove cluster from `disabledClusters`, re-stage |
| `reset` | Delete `.gsd-surface.json`, return to install-time profile |
| *(none)* | Treat as `list` |

---

## list / status

Call `listSurface(runtimeConfigDir, manifest, CLUSTERS)` from
`get-shit-done/bin/lib/surface.cjs`. Display:

```
Enabled (N skills, ~T tokens):
  core_loop:   new-project  discuss-phase  plan-phase  execute-phase  help  update
  audit_review: …
  …

Disabled:
  utility:  health  stats  settings  …

Token cost: ~T (budget cap ~500 tokens for 200k context @ 1%)
```

For `status` also append:

```
Base profile:   standard  (from .gsd-surface.json)
Install profile: standard  (from .gsd-profile)
```

---

## profile \<name\>

1. Read current surface: `readSurface(runtimeConfigDir)` → if null, seed from `readActiveProfile(runtimeConfigDir)`.
2. Set `surfaceState.baseProfile = name`.
3. `writeSurface(runtimeConfigDir, surfaceState)`.
4. Resolve and re-apply: `applySurface(runtimeConfigDir, commandsDir, agentsDir, manifest, CLUSTERS)`.
5. Confirm: "Surface updated to profile `<name>`. N skills enabled."

---

## disable \<cluster\>

Valid cluster names: `core_loop`, `audit_review`, `milestone`, `research_ideate`,
`workspace_state`, `docs`, `ui`, `ai_eval`, `ns_meta`, `utility`.

1. Validate cluster name against `Object.keys(CLUSTERS)`.
2. Read or initialize surface state.
3. Add cluster to `surfaceState.disabledClusters` (deduplicate).
4. `writeSurface` → `applySurface`.
5. Confirm: "Disabled cluster `<cluster>`. N skills removed from surface."

---

## enable \<cluster\>

1. Read surface state; if null, nothing to enable — print "No surface delta active."
2. Remove cluster from `surfaceState.disabledClusters`.
3. `writeSurface` → `applySurface`.
4. Confirm: "Enabled cluster `<cluster>`. N skills added back to surface."

---

## reset

1. Check if `.gsd-surface.json` exists.
2. Delete it.
3. Re-apply using only `readActiveProfile(runtimeConfigDir)` (install-time profile).
4. Confirm: "Surface reset to install-time profile `<name>`."

---

## runtimeConfigDir resolution

```bash
# Claude Code
RUNTIME_CONFIG_DIR=$HOME/.codex/skills

# Resolve commandsDir and agentsDir
COMMANDS_DIR=$HOME/.codex/commands/gsd
AGENTS_DIR=$HOME/.codex/agents
```

All paths can be overridden by reading the `CLAUDE_CONFIG_DIR` env var if set.

---

## Error handling

- Unknown cluster name → list valid cluster names, exit without writing.
- Unknown profile name → list known profiles (`core`, `standard`, `full`), exit.
- Missing `surface.cjs` → prompt: "Run `npm i -g get-shit-done` to reinstall GSD."

<execution_context>
Surface state file: `$HOME/.codex/skills/.gsd-surface.json`
Install profile marker: `$HOME/.codex/skills/.gsd-profile`
Engine module: `$HOME/.codex/get-shit-done/bin/lib/surface.cjs`
Cluster definitions: `$HOME/.codex/get-shit-done/bin/lib/clusters.cjs`
</execution_context>
