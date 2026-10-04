#!/usr/bin/env bash
# KDE tiling: Krohnkite + Alt key scheme + right-Alt-as-Alt (Plasma 6)
# Captured 2026-09-30 from the live ZBook setup. Idempotent, safe to re-run.
# KWin reads shortcut bindings ONLY at login -> run this, then log out/in once.
#
# WARNING (Plasma 6.6 on this machine): the kglobalaccel DBus query methods
# actionList / globalShortcutsByKey abort kwin_wayland (QKeySequence
# demarshall). Do not call them; use the Shortcuts GUI or this script.
set -euo pipefail
say() { printf '\n== %s\n' "$*"; }

# 1) Krohnkite. krohnkite.com points at the abandoned Plasma 5 repo; the
#    maintained Plasma 6 fork lives on Codeberg (pin a release, check for newer).
if ! kpackagetool6 -t KWin/Script -s krohnkite >/dev/null 2>&1; then
  say "installing Krohnkite 0.9.9.2 (Codeberg fork)"
  tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/krohnkite.kwinscript" \
    "https://codeberg.org/anametologin/Krohnkite/releases/download/0.9.9.2/krohnkite-0.9.9.2-1d7fd74.kwinscript"
  kpackagetool6 -t KWin/Script -i "$tmp/krohnkite.kwinscript"
  rm -rf "$tmp"
else
  say "Krohnkite already installed"
fi
# Do NOT toggle the script on/off at runtime: reload cycles crash apps.
# It loads once at login. update later with: kpackagetool6 -t KWin/Script -u <file>.kwinscript
kwriteconfig6 --file kwinrc --group Plugins --key krohnkiteEnabled true

# 2) Global shortcut bindings (kglobalshortcutsrc): value = active,default,description
python3 - "$HOME/.config/kglobalshortcutsrc" <<'PYEOF'
import json, os, re, sys
payload = json.loads(r'''{"KrohnkiteDecrease": ["kwin", "Alt+D", "none", "Krohnkite: Decrease"], "KrohnkiteFloatAll": ["kwin", "Alt+Shift+F", "none", "Krohnkite: Toggle Float All"], "KrohnkiteFocusDown": ["kwin", "Alt+J", "none", "Krohnkite: Focus Down"], "KrohnkiteFocusLeft": ["kwin", "Alt+H", "none", "Krohnkite: Focus Left"], "KrohnkiteFocusNext": ["kwin", "Alt+.", "none", "Krohnkite: Focus Next"], "KrohnkiteFocusPrev": ["kwin", "Alt+\\\\", "", "none,Krohnkite: Focus Previous"], "KrohnkiteFocusRight": ["kwin", "Alt+L", "none", "Krohnkite: Focus Right"], "KrohnkiteFocusUp": ["kwin", "Alt+K", "none", "Krohnkite: Focus Up"], "KrohnkiteGrowHeight": ["kwin", "Alt+Ctrl+J", "none", "Krohnkite: Grow Height"], "KrohnkiteIncrease": ["kwin", "Alt+I", "none", "Krohnkite: Increase"], "KrohnkiteMonocleLayout": ["kwin", "Alt+M", "none", "Krohnkite: Monocle Layout"], "KrohnkiteNextLayout": ["kwin", "Alt+\\\\\\\\", "none", "Krohnkite: Next Layout"], "KrohnkitePreviousLayout": ["kwin", "Alt+|", "none", "Krohnkite: Previous Layout"], "KrohnkiteRotate": ["kwin", "Alt+R", "none", "Krohnkite: Rotate"], "KrohnkiteRotatePart": ["kwin", "Alt+Shift+R", "none", "Krohnkite: Rotate Part"], "KrohnkiteSetMaster": ["kwin", "Alt+Shift+Return", "none", "Krohnkite: Set master"], "KrohnkiteShiftDown": ["kwin", "Alt+Shift+J", "none", "Krohnkite: Move Down/Next"], "KrohnkiteShiftLeft": ["kwin", "Alt+Shift+H", "none", "Krohnkite: Move Left"], "KrohnkiteShiftRight": ["kwin", "Alt+Shift+L", "none", "Krohnkite: Move Right"], "KrohnkiteShiftUp": ["kwin", "Alt+Shift+K", "none", "Krohnkite: Move Up/Prev"], "KrohnkiteShrinkHeight": ["kwin", "Alt+Ctrl+K", "none", "Krohnkite: Shrink Height"], "KrohnkiteShrinkWidth": ["kwin", "Alt+Ctrl+H", "none", "Krohnkite: Shrink Width"], "KrohnkiteTileLayout": ["kwin", "Alt+T", "none", "Krohnkite: Tile Layout"], "KrohnkiteToggleFloat": ["kwin", "Alt+F", "none", "Krohnkite: Toggle Float"], "KrohnkitegrowWidth": ["kwin", "Alt+Ctrl+L", "none", "Krohnkite: Grow Width"], "Switch to Desktop 1": ["kwin", "Alt+1", "Meta+F1\\tCtrl+F1", "Switch to Desktop \u0661"], "Switch to Desktop 10": ["kwin", "Alt+0", "", "Switch to Desktop \u0661\u0660"], "Switch to Desktop 2": ["kwin", "Alt+2", "Meta+F2\\tCtrl+F2", "Switch to Desktop \u0662"], "Switch to Desktop 3": ["kwin", "Alt+3", "Meta+F3\\tCtrl+F3", "Switch to Desktop \u0663"], "Switch to Desktop 4": ["kwin", "Alt+4", "Meta+F4\\tCtrl+F4", "Switch to Desktop \u0664"], "Switch to Desktop 5": ["kwin", "Alt+5", "", "Switch to Desktop \u0665"], "Switch to Desktop 6": ["kwin", "Alt+6", "", "Switch to Desktop \u0666"], "Switch to Desktop 7": ["kwin", "Alt+7", "", "Switch to Desktop \u0667"], "Switch to Desktop 8": ["kwin", "Alt+8", "", "Switch to Desktop \u0668"], "Switch to Desktop 9": ["kwin", "Alt+9", "", "Switch to Desktop \u0669"], "_launch": ["services.org.kde.konsole.desktop", "Alt+Return", "Ctrl+Alt+T", "Konsole"]}''')
path = sys.argv[1]
os.makedirs(os.path.dirname(path), exist_ok=True)
lines = open(path, encoding='utf-8').read().split('\n') if os.path.exists(path) else []
done = set()
out = []
cur = ''
for ln in lines:
    s = ln.strip()
    if s.startswith('[') and s.endswith(']'):
        cur = '.'.join(re.findall(r'\[([^\]]+)\]', s))
        out.append(ln)
        continue
    m = re.match(r'^([^#=]+)=(.*)$', ln)
    if m and cur in [v[0] for v in payload.values()] and m.group(1) in payload and payload[m.group(1)][0] == cur:
        _, a, d, desc = payload[m.group(1)]
        out.append(f'{m.group(1)}={a},{d},{desc}')
        done.add(m.group(1))
    else:
        out.append(ln)
bypend = {}
for k, v in payload.items():
    if k not in done:
        bypend.setdefault(v[0], []).append(k)
for sec, ks in bypend.items():
    header = ''.join('[' + p + ']' for p in sec.split('.'))
    block = [header] + [f'{k}={payload[k][1]},{payload[k][2]},{payload[k][3]}' for k in ks]
    if header in out:
        i = out.index(header)
        out[i + 1:i + 1] = block[1:]
    else:
        out += [''] + block
open(path, 'w', encoding='utf-8').write('\n'.join(out))
print(f'shortcuts: {len(payload)} bindings ensured')
PYEOF

# 3) Right Alt = plain Alt (XKB lv3:ralt_alt). NOTE: this drops AltGr special
#    characters (harakat etc.) on the eg Arabic layout -- both Alts become Alt.
kwriteconfig6 --file kxkbrc --group Layout --key Options lv3:ralt_alt

say "done -- log out and back in once (KWin reads shortcuts at login)"
