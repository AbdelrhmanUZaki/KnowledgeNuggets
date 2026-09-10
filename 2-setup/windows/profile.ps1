# PowerShell profile (Windows) -- port of the macOS ~/.bashrc
# Symlink/copy into:
#   PS 7:  ~\Documents\PowerShell\Microsoft.PowerShell_profile.ps1
#   PS 5.1: ~\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1

# Editor
Set-Alias -Name vi -Value nvim
Set-Alias -Name vim -Value nvim

# Git shortcuts
function gst { git status --short }
function gco { git checkout @args }
function gcm { git commit -m @args }
function gl   { git log --oneline --graph --all --decorate }
function gd   { git diff @args }
function ga   { git add @args }

# Listing
function ll { Get-ChildItem -Force | Format-Table -AutoSize }
function la { Get-ChildItem -Force }
function l  { Get-ChildItem }

# Navigation
function mkcd($Path) {
  New-Item -ItemType Directory -Force -Path $Path | Out-Null
  Set-Location -LiteralPath $Path
}
function .. { Set-Location .. }
function ... { Set-Location ..\.. }

# Python venv helper (Windows layout)
function venv { & .\.venv\Scripts\Activate.ps1 }

# Colorized grep (ripgrep preferred; fall back to Select-String)
function grep { rg @args }

# Which
function which($Name) { Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source }

# opencode
Set-Alias -Name oc -Value opencode

# History + vi mode
Set-PSReadLineOption -EditMode Vi
Set-PSReadLineOption -HistorySearchCursorMovesToEnd:$true

# Prompt with git branch (port of parse_git_branch + PS1)
function prompt {
  $branch = git rev-parse --abbrev-ref HEAD 2>$null
  $git = if ($LASTEXITCODE -eq 0 -and $branch) { "[$branch] " } else { "" }
  $loc = (Get-Location).Path -replace [regex]::Escape($HOME), '~'
  "$loc $git> "
}
