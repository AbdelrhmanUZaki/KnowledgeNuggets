# wifi-failover — instant WiFi failover to the phone hotspot

The home router (`$FAILOVER_ROUTER_SSID`) loses internet every 10–40 minutes for a few
minutes, then recovers. **The WiFi link itself stays up** — only the router's
WAN dies — so nothing in the OS fires an event, and every program keeps
hanging. `wifi-failover` detects the outage in ~2–5 seconds, switches the
WiFi to the phone hotspot (`$FAILOVER_HOTSPOT_SSID`), and switches back to the router as
soon as its internet works again.

```
router WAN dies ──► stream-ping misses 3 replies (~2s)
                     ──► confirm: all 3 targets dead (1s each)
                     ──► nmcli up hotspot          ──► notify-send
                     ──► every 90s+: try router, internet must hold
                         a 45s stability window ──► switch back + notify
                         (a return that dies <2min later backs off
                          the next try: 90s → 180s → 360s → 600s)
```

## Why polling (and why it is still instant)

There is no kernel/D-Bus event for "internet behind the router is gone":
the kernel only sees link/IP/route changes, and NetworkManager's own
connectivity check polls every ~5 minutes anyway. So some probing is
unavoidable — the trick is a **continuous ping stream** at 2 probes/second
(`ping -i 0.5 -O`), reacting to missed replies as they arrive:

- detection ≈ 2s of silence + a confirmation round against 3 targets
  (~2–5s total, measured 2s in a forced-outage test)
- cost: one 64-byte ICMP packet every 0.5s
- false positives: needs ~2s of total silence **and** all 3 targets
  (1.1.1.1, 8.8.8.8, 9.9.9.9) dead — a single WiFi hiccup never triggers it

## Install

Symlink from the repo so it stays the source of truth (like `vmup`):

```bash
mkdir -p ~/.local/bin ~/.config/systemd/user
ln -sf ~/Documents/Github/KnowledgeNuggets/2-setup/linux/wifi-failover/wifi-failover.sh ~/.local/bin/wifi-failover.sh
ln -sf ~/Documents/Github/KnowledgeNuggets/2-setup/linux/wifi-failover/wifi-failover.service ~/.config/systemd/user/wifi-failover.service
systemctl --user daemon-reload
systemctl --user enable --now wifi-failover
```

Requires: NetworkManager (`nmcli`), `ping`, `notify-send`. No root — the
user session is allowed to activate WiFi connections via polkit.

## Daily commands

| Command | Effect |
|---|---|
| `systemctl --user status wifi-failover` | is it running |
| `tail -f ~/.local/state/wifi-failover.log` | live log of checks/switches |
| `systemctl --user stop/start/restart wifi-failover` | control it |

## Behavior

- On the router: stream-ping; on confirmed outage → hotspot + desktop
  notification.
- On the hotspot: retries the router every 90s; each retry briefly hops to
  the router and requires its internet to **hold a 45s stability window**
  before committing back. Two anti-flap guards exist because the router's
  WAN sometimes recovers for only seconds at a time:
  1. *Stability window* — one lucky ping round is not enough to commit back.
  2. *Dwell memory* — a return that dies sooner than 2 min after commit
     counts as failed and **doubles the delay before the next try**
     (90s → 180s → 360s → 600s cap). A return that holds ≥2 min resets it
     to 90s. With a badly flapping WAN this converges to one short probe
     every 10 min instead of constant bouncing.
- Hotspot unreachable (phone off / out of range): stays on the router,
  notifies, retries the switch every 60s.
- Connected to some other WiFi by hand: the script stays idle and never
  fights the manual choice.
- If the stream-ping target alone goes silent but the internet is fine
  (target blocking ICMP), it rotates to a target that answers and keeps
  watching.

## Tuning (environment variables, `FAILOVER_*`)

| Variable | Default | Meaning |
|---|---|---|
| `FAILOVER_PROBE_INTERVAL` | `0.5` | seconds between stream pings (floor 0.2 unprivileged) |
| `FAILOVER_MISS_THRESHOLD` | `3` | missed replies before the confirm round |
| `FAILOVER_CONFIRM_TIMEOUT` | `1` | per-target timeout of the confirm round |
| `FAILOVER_ROUTER_SSID` / `FAILOVER_HOTSPOT_SSID` | (required) | the two networks; the script exits until both are set |
| `FAILOVER_SWITCH_BACK_EVERY` | `90` | seconds between router retries on hotspot |
| `FAILOVER_SWITCH_BACK_STABLE` | `45` | seconds the router's internet must hold before committing back |
| `FAILOVER_STABLE_CHECK_STEP` | `5` | spacing of the checks inside the stability window |
| `FAILOVER_STABLE_ALLOWED_MISS` | `1` | failed checks tolerated inside the window |
| `FAILOVER_MIN_GOOD_DWELL` | `120` | a return dying sooner than this backs off the next try |
| `FAILOVER_MAX_RETRY_INTERVAL` | `600` | cap for the escalating retry delay after failed returns |
| `FAILOVER_PING_TARGETS` | `1.1.1.1 8.8.8.8 9.9.9.9` | confirm-round targets |

Testing trick: point `FAILOVER_PING_TARGETS` at a dead address
(e.g. `192.0.2.1`) and shorten the intervals — the script will run a full
switch/hop-back cycle on demand. The `wifi-failover.service` unit sets no
variables, so the defaults above apply in production.

## Troubleshooting

**"It keeps switching router <-> hotspot constantly"** — that is the router's
WAN flapping on a seconds scale (log shows "internet is back" then
"confirmed down" seconds later, repeatedly). The two anti-flap guards exist
for exactly this: the stability window and the dwell-memory backoff
("router held only Ns (< 120s), next try in Ns" in the log). If it still
flaps too much for your taste, raise `FAILOVER_SWITCH_BACK_EVERY`,
`FAILOVER_SWITCH_BACK_STABLE`, and `FAILOVER_MAX_RETRY_INTERVAL`. The real
fix is the router itself — reboot it / check the ISP line.

**Hotspot switch fails** (`could not connect to hotspot` in the log) — the
phone hotspot is off or out of range. The script stays on the router and
retries every 60s.

## Files

- `wifi-failover.sh` — the script (symlinked to `~/.local/bin/wifi-failover.sh`)
- `wifi-failover.service` — systemd user unit, `Restart=always`
  (symlinked to `~/.config/systemd/user/wifi-failover.service`)
- Log: `~/.local/state/wifi-failover.log` (not in the repo)
