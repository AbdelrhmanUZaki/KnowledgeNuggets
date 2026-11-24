# Networking (if needed)

## Static IP + DNS

Assign `192.168.1.50`, gateway `192.168.1.1`, Cloudflare DNS (`1.1.1.1`, `1.0.0.1`) on interface `enp0s3`:

```bash
nmcli con modify "enp0s3-autoconnect" ipv4.addresses 192.168.1.50/24
nmcli con modify "enp0s3-autoconnect" ipv4.gateway 192.168.1.1
nmcli con modify "enp0s3-autoconnect" ipv4.dns "1.1.1.1 1.0.0.1"
nmcli con modify "enp0s3-autoconnect" ipv4.method manual
nmcli con down "enp0s3-autoconnect" && nmcli con up "enp0s3-autoconnect"
```

### Undo (back to DHCP)

```bash
nmcli con modify "enp0s3-autoconnect" ipv4.addresses ""
nmcli con modify "enp0s3-autoconnect" ipv4.gateway ""
nmcli con modify "enp0s3-autoconnect" ipv4.dns ""
nmcli con modify "enp0s3-autoconnect" ipv4.method auto
nmcli con down "enp0s3-autoconnect" && nmcli con up "enp0s3-autoconnect"
```

> Replace `enp0s3-autoconnect` with your actual connection name: `nmcli con show`

## WiFi failover to phone hotspot

Router WAN dies every 10–40 min while the WiFi link stays up — no OS event
fires for that, so a systemd user service stream-pings at 2 probes/s,
confirms across 3 targets, and switches to the hotspot in ~2–5s; it hops
back when the router recovers. Hotspot SSID must be broadcasting (phone on),
otherwise it stays on the router and retries every 60s.

- Script + unit + full docs: [`linux/wifi-failover/`](linux/wifi-failover/README.md)
- Live log: `tail -f ~/.local/state/wifi-failover.log`
- Status: `systemctl --user status wifi-failover`