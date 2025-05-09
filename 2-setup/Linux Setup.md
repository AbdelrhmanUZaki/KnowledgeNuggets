### Download ParrotOS (HTB Edition)

Get the ISO from [Parrot-htb-6.3.2_amd64.iso](https://deb.parrot.sh/parrot/iso/6.3.2/Parrot-htb-6.3.2_amd64.iso)

---
### Install Essential Applications

```bash
# Update your system first
sudo apt update && sudo apt upgrade

# Install apps
sudo apt install -y rofi nala tmux xclip konsole seclists
```

#### App Overview:

- **`nala`**: A modern front-end for `apt` with a cleaner UI.
- **`rofi`**: A fast application launcher.
- **`konsole`**: Make sure to set the suitable font size and the Nerd font for nvim.
    

> Set a shortcut in **Keyboard Settings** to open Rofi:  
> `Super + Space` → Command: `rofi -show drun`

---

### Nvim

```
wget https://github.com/neovim/neovim/releases/download/v0.11.0/nvim-linux-x86_64.appimage

chmod +x nvim-linux-x86_64.appimage

sudo mv nvim-linux-x86_64.appimage /usr/bin/nvim

# Nerd Font Section

wget https://github.com/ryanoasis/nerd-fonts/releases/download/v3.3.0/Agave.zip
unzip Agave.zip -d ~/Agave
sudo mkdir -p /usr/share/fonts/truetype/nerd-fonts
sudo cp ~/Agave/*.ttf /usr/share/fonts/truetype/nerd-fonts/
sudo fc-cache -fv


sudo nala install ripgrep gcc make

git clone https://github.com/NvChad/starter ~/.config/nvim && nvim
```

- Run `:MasonInstallAll` command after lazy.nvim finishes downloading plugins.
- Delete the `.git` folder from nvim folder.
- Learn customization of ui & base46 from `:h nvui`.
##### Update

- `Lazy sync` nvim command

#### Add as `~/.config/nvim/:

The [nvim config](attachments/nvim%20config.zip) in attachments folder.

---
### Install Brave Browser

```bash
curl -fsS https://dl.brave.com/install.sh | sh
```

---
### Install VS Code from this [Source](https://code.visualstudio.com/docs/setup/linux)

```bash
sudo apt install ./<file>.deb
```

---
### Customize Your Shell

#### Add to `~/.bashrc`:

```bash
# Vim
alias vi=nvim
set -o vi  # Enable Vim keybindings in terminal

# Terminal Shortcuts
alias c=clear
alias h=history
alias hs="history | grep"
alias grep='grep --color'

# Directory & File
alias md=mkdir
alias df='df -h'
alias ..='cd ..'

# System Management
alias u='sudo nala update && sudo nala upgrade'
alias install='sudo nala install'
alias r='sudo nala remove'
alias search='sudo nala search'
alias reboot='systemctl reboot'
alias poweroff='systemctl poweroff'
alias suspend='systemctl suspend'

# Config Management
alias ed='vi ~/.bashrc'
alias ref='source ~/.bashrc'

# Networking
alias p='ping google.com'
alias myip="ip -4 addr show \$(ip route show default | awk '/default/ {print \$5}') | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'"

# Git
alias gc='git commit -m '
alias gst='git status'

# Exports
export EDITOR=vim
export TERM=xterm-256color
```

---

#### Add to `~/.profile`:

```bash
# Remap Caps Lock to Escape (great for Vim usage)
setxkbmap -option caps:escape
```

---
#### Add to `~/.tmux.conf`:

```bash
# Enable vim key binding in command line editing as in .bashrc
set-option -g default-command "bash -c 'set -o vi; exec bash'"  
  
# Enable mouse support for interaction with tmux panes
set -g mouse on

# Bind 'y' to copy selected text to system clipboard using xclip
bind-key -T copy-mode-vi y send-keys -X copy-pipe-and-cancel "xclip -selection clipboard -in"

# Automatically copy mouse selection to system clipboard using xclip
bind-key -T copy-mode-vi MouseDragEnd1Pane \
  send-keys -X copy-pipe-and-cancel "xclip -selection clipboard -in"

```

- To Reload tmux without restarting `tmux source-file ~/.tmux.conf`
- Copy/Paste
	- Default Settings
		- Enter copy mode: `Ctrl + B` then `[`
		- Use Vim keys to move around
		- Press `Enter` to copy selection
		- Paste from buffer: `Ctrl + B` then `]`
	- My edits
		- `Y` to copy instead of `Enter`
		- When selecting with mouse or copying with keyboard, it now automatically copied into system clipboard.
- Panes
	- `Ctrl + B` then `O` switch focus between Panes.
	- `Ctrl + BO` switch focus between Panes.

---
#### If needed

- Configure IPv4 and DNS
	- Use the following commands to assign a static IP (`192.168.1.50`), set the gateway (`192.168.1.1`), and configure Cloudflare DNS (`1.1.1.1`, `1.0.0.1`) on the `enp0s3` interface:
		```bash
		nmcli con modify "enp0s3-autoconnect" ipv4.addresses 192.168.1.50/24
		nmcli con modify "enp0s3-autoconnect" ipv4.gateway 192.168.1.1
		nmcli con modify "enp0s3-autoconnect" ipv4.dns "1.1.1.1 1.0.0.1"
		nmcli con modify "enp0s3-autoconnect" ipv4.method manual
		nmcli con down "enp0s3-autoconnect" && nmcli con up "enp0s3-autoconnect"
		```
	- To undo it use:
		```bash
		nmcli con modify "enp0s3-autoconnect" ipv4.addresses ""
		nmcli con modify "enp0s3-autoconnect" ipv4.gateway ""
		nmcli con modify "enp0s3-autoconnect" ipv4.dns ""
		nmcli con modify "enp0s3-autoconnect" ipv4.method auto
		nmcli con down "enp0s3-autoconnect" && nmcli con up "enp0s3-autoconnect"
		```