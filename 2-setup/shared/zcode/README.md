# zcode

Global config for the ZCode CLI. Only two files are portable; both are symlinked into `~/.zcode` by each OS restore script ([`../../linux/restore.sh`](../../linux/restore.sh) / [`../../macos/restore.sh`](../../macos/restore.sh) / [`../../windows/restore.ps1`](../../windows/restore.ps1)).

| File | Restored to | Purpose |
|---|---|---|
| `AGENTS.md` | `~/.zcode/AGENTS.md` | User default instructions — [rtk](https://github.com/rtk-ai/rtk) output-condensing rules |
| `cli/config.json` | `~/.zcode/cli/config.json` | Hooks — rtk `PreToolUse` on `Bash` |

Everything else in `~/.zcode` is machine-local and intentionally not synced: `v2/` desktop settings/credentials, `cli/agents/` session dirs, `cli/plugins/` cache. Plugin marketplaces are re-added by hand (`/plugin marketplace add ...`).

Because the live files are symlinks into this repo, changes the app or `rtk` writes here (e.g. a new `rtk-instructions` version) show up as git changes — commit them like any other config tweak.
