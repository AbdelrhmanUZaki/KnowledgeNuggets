# Manual Steps (one-time, per machine)

These can't be safely automated (login/session automation is an anti-pattern).

## 1. Brave / browser

1. Open Browser e.g. Brave and **sign into your Brave account** → extensions, bookmarks, history, passwords sync automatically. This one step replaces ~10 manual reinstalls.
2. Verify the extensions you use (e.g. Bitwarden, uBlock, Wappalyzer) came back.

## 2. Password manager

- Install the **Bitwarden** extension, unlock with master password (and 2FA). Vault restores automatically - no re-entry of every password.

## 3. Logins

- **Gmail / Google**: 2FA (authenticator app or passkey)
- **GitHub**: `gh auth login` (OAuth). For SSH-based workflows, generate a key: `ssh-keygen -t ed25519 -C "you@example.com"` and add to github.com/settings/keys.
- **X / Twitter**: standard login (OTP if enabled)

## 4. Chat

- **Telegram**: installed via `install.sh` (snap). Quick login by scanning the QR code (or mobile number + code).
- **WhatsApp Web**: open web.whatsapp.com, scan QR with your phone. Expected: ~5 seconds.

## 5. VS Code

From <https://code.visualstudio.com/docs/setup/linux>. Skip if you live in nvim:

```bash
sudo apt install ./<file>.deb
```

Sign into Settings Sync / your Microsoft or GitHub account to restore extensions + settings.

## 6. Caps Lock → Escape (Xorg)

Only with XOrg. Add to `~/.profile`:

```bash
# Remap Caps Lock to Escape (great for Vim usage)
setxkbmap -option caps:escape
```

## 7. Tmux cheatsheet

- Reload without restart: `tmux source-file ~/.tmux.conf`
- Copy mode: `Ctrl + B` then `[`, Vim keys to move, `y` to copy (copies to system clipboard automatically, and mouse-selection copies too)
- Paste: `Ctrl + B` then `]`
- Switch focus between panes: `Ctrl + B` then `o`