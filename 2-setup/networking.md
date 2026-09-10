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