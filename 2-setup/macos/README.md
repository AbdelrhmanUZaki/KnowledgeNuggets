# macOS setup

macOS dotfiles and tools. Full fresh-install checklist: [macOS Setup.md](macOS%20Setup.md).

| Item | Purpose |
|---|---|
| `bashrc`, `bash_profile` | Shell |
| `tmux.conf` | tmux (linked as `~/.tmux.conf.local`) |
| `yabai/`, `skhd/` | Tiling window manager + hotkeys |
| `karabiner/` | Karabiner config (Caps = Esc + scroll, Space = nav) |
| `warp/` | Warp terminal settings |
| `launchdaemons/` | kanata LaunchDaemon plist (edit `<USERNAME>` before installing) |
| `restore.sh` | Symlink everything above (plus [`../shared/`](../shared/)) into `$HOME` |

Cross-OS configs live in [`../shared/`](../shared/README.md).
