# vmup — one-command sandboxed VM for AI coding agents (agent-vm + ZCode)

`vmup` gives every project directory its own **isolated Linux VM** and a
**stable SSH address** for connecting the ZCode desktop app to it via
**Remote Development (SSH)** — so the agent's shell, docker, and file edits
all happen inside the VM, never on the host.

```
┌─────────────────────┐         SSH (127.0.0.1:<pinned port>)        ┌──────────────────────────┐
│  ZCode GUI (host)   │ ───────────────────────────────────────────► │  project VM (QEMU/KVM)   │
│  login + settings   │                                             │  Debian 13, docker, node │
└─────────────────────┘                                             │  mounts: project dir only│
                                                                    └──────────────────────────┘
```

## Why this stack

- **The problem**: running an AI coding agent directly on the host means it can
  touch everything. Colima (Docker-in-VM) crashed repeatedly with a QEMU
  networking assertion (`net_fill_rstate: Assertion 'size == 0'`) in the
  `-netdev socket` path — see Troubleshooting below.
- **The fix**: [agent-vm](https://github.com/sylvinus/agent-vm) — per-project
  Debian VMs managed by [Lima](https://lima-vm.io) using plain slirp
  networking (`-netdev user`), a different code path from the crashing one.
  Audited (all shell, no host-side sudo/network effects; provisioning runs
  inside the guest from canonical vendor endpoints only).
- **vmup wraps** agent-vm to add the two things it lacks for a GUI-agent
  workflow: a **deterministic SSH port** and an **`~/.ssh/config` alias** that
  ZCode's connection wizard can auto-fill.

## Prerequisites (one-time)

```bash
# QEMU + KVM access
sudo apt install qemu-system-x86
sudo usermod -aG kvm "$USER"   # then re-login

# Lima (limactl) — from https://lima-vm.io/docs/installation/
limactl --version

# agent-vm
git clone https://github.com/sylvinus/agent-vm ~/github/agent-vm
cd ~/github/agent-vm && ./install.sh

# Build the base VM template once (~10 min; preinstalled software is
# inherited by every project VM cloned from it)
agent-vm setup --preinstall=python,node,docker,gh
```

## Install vmup

Symlink it onto PATH so the repo stays the source of truth:

```bash
mkdir -p ~/.local/bin
ln -sf ~/github/KnowledgeNuggets/2-setup/linux/vmup/vmup ~/.local/bin/vmup
```

## Usage

```bash
cd ~/github/<project>
vmup
```

Output (first run creates the VM; later runs are instant no-ops):

```
VM:      agent-vm-<project>-<hash8>  (running)
SSH:     ssh vm-<project>
ZCode:   Projects '+' → Remote Connection → SSH → alias 'vm-<project>'
Stop:    agent-vm stop   (port stays pinned for next time)
```

Then in ZCode: **Projects → + → Remote Connection → SSH**, pick the alias
`vm-<project>` (auto-fills host/port/user/key), connect, wait for the one-time
server install into the VM, and select the project directory as the workspace
(same path as on the host — it's the live mount).

Daily commands:

| Command | Effect |
|---|---|
| `vmup` | create/start this project's VM, pin port, refresh alias |
| `ssh vm-<project>` | plain shell into the VM |
| `agent-vm stop` | stop the VM (frees RAM; port stays pinned) |
| `agent-vm status` / `list` | fleet overview |
| `agent-vm rm` | destroy this project's VM |
| `agent-vm --readonly shell` | session with the project dir mounted read-only |
| `agent-vm --offline shell` | session with VM networking cut off |

## After a reboot

VMs never auto-start on boot, on purpose: a running VM holds its RAM
(3 GiB default) and CPUs whether you use it or not, and you rarely want
*all* project VMs up at once. Starting is on demand, one command:

```bash
cd ~/github/<project> && vmup   # starts the VM (alias/port verified too)
# or: agent-vm shell            # same, plus drops you into a VM shell
```

Then in ZCode: click the **refresh button beside the folder name** in the
sidebar to reconnect the workspace. (Want one project always up? A systemd
`--user` unit running `limactl start <vm>` does it — opt-in only.)

## How the "fixed port" works

- agent-vm names each VM `agent-vm-<basename>-<first 8 hex of
  sha256(abs-path)>`. `vmup` pins `.ssh.localPort` in that VM's `lima.yaml`
  to `46000 + (hash % 1000)` — deterministic per project path.
- Because the pin lives in the instance config it **survives reboots and
  stop/start cycles**, and because it is derived from the path hash it is
  **re-derived identically after `rm`/`--reset`**. Collisions with ports
  pinned by other VMs or already listening are nudged +1.
- `~/.ssh/config` gets one managed block per alias
  (`# BEGIN/END agent-vm alias: …`) rewritten on every `vmup` run, so stale
  ports never linger.

## Security model (what the VM can and cannot see)

- **One folder only**: the base template is created with `mounts: []`; a
  project VM mounts exactly the project directory (read-write, via sshfs) at
  the same path. Verify anytime inside the VM:
  `findmnt ~/github/<project>` should be the only host-backed mount.
- **No secrets in the VM by default**: agent-vm only pushes secrets if you
  create `~/.agent-vm/env` (mode 600) or add entries to `~/.agent-vm/volumes`
  — both are opt-in; leave them absent to keep the surface at one folder.
  ZCode's model login never enters the VM (it stays in the desktop app).
- **Nothing secret in this repo**: the SSH key lives at
  `~/.lima/_config/user` on the host only; vmup references the path, never
  the key material.
- Filesystem ≠ network: like any LAN machine, the VM can reach host network
  services. Use `--offline` when that matters. A VM is a blast-radius limiter,
  not an adversarial boundary (see Trail of Bits, "VMs won't contain
  cyber-capable agents").

## Troubleshooting

**`agent-vm setup` dies with `failed to download …nerdctl…: expected digest …, got ''`**
Lima's downloader has no patience for slow GitHub routes. Pre-seed its cache —
note the digest-marker gotcha: Lima compares against the `sha256.digest`
*marker file* next to the data, so both are needed:

```bash
url=https://github.com/containerd/nerdctl/releases/download/v2.3.5/nerdctl-full-2.3.5-linux-amd64.tar.gz
d="$HOME/.cache/lima/download/by-url-sha256/$(echo -n "$url" | sha256sum | cut -d' ' -f1)"
mkdir -p "$d"
curl -fL --retry 8 --retry-all-errors -C - -o "$d/data" "$url"
printf 'sha256:<expected-digest-from-the-error>\n' > "$d/sha256.digest"
```

**Port changed after all** — run `vmup` again; it re-reads the pinned port and
rewrites the alias. Check the source of truth with `limactl list`.

**`Error: project path contains whitespace`** — Lima cannot mount paths with
spaces; rename the directory.

## Files

- `vmup` — the script (symlinked to `~/.local/bin/vmup`)
