# Linux setup

Linux dotfiles and tools (ParrotOS / Debian / Ubuntu). Full fresh-install checklist: [Linux Setup.md](Linux%20Setup.md).

| Item | Purpose |
|---|---|
| `bashrc`, `bash_profile` | Shell (aliases, PATH, rtk-friendly prompt env) |
| `tmux.conf` | tmux |
| `kanata.kbd` | Keyboard remap: caps = tap Esc / hold scroll layer, space hold = nav arrows |
| `restore.sh` | Symlink everything above (plus [`../shared/`](../shared/)) into `$HOME` |
| [`vmup/`](vmup/) | Sandbox VMs for AI agents (Lima + agent-vm + ZCode Remote SSH) |

Cross-OS configs live in [`../shared/`](../shared/README.md).
