# Restore Windows dotfiles + shared configs.
# Route: 2-setup/windows/restore.ps1
# Safe to re-run; backups go to ~\.dotfiles-backup-<timestamp>\

$ErrorActionPreference = "Stop"
$Win = $PSScriptRoot
$Setup = Split-Path $Win -Parent
$Shared = Join-Path $Setup "shared"
$Backup = Join-Path $HOME (".dotfiles-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))

function Link-File {
    param([string]$Src, [string]$Dst)
    $item = Get-Item $Dst -Force -ErrorAction SilentlyContinue
    if ($item -and $item.LinkType -eq "SymbolicLink") {
        # Resolve target; the link is broken if Get-Item on the target fails
        $resolved = (Resolve-Path $Dst -ErrorAction SilentlyContinue) -ne $null
        if ($resolved) {
            Write-Host "skip   $Dst (already a symlink)"
        } else {
            Remove-Item $Dst -Force
            Write-Host "heal   $Dst (was a broken link, re-pointing)"
        }
    } elseif ($item) {
        New-Item -ItemType Directory -Force -Path $Backup | Out-Null
        Move-Item $Dst (Join-Path $Backup (Split-Path $Dst -Leaf))
        New-Item -ItemType SymbolicLink -Path $Dst -Target $Src -Force | Out-Null
        Write-Host "backup $Dst -> $Backup"
    } else {
        New-Item -ItemType SymbolicLink -Path $Dst -Target $Src -Force | Out-Null
        Write-Host "linked $Dst -> $Src"
    }
}

# Linux/macOS/Windows all use ~/.config for the "shared" opencode/codex dirs;
# on Windows opencode/codex read from UserProfile. Symlinking works for both.
Write-Host "== Windows dotfiles =="
Link-File (Join-Path $Win "profile.ps1")                 "$HOME\Documents\PowerShell\Microsoft.PowerShell_profile.ps1"
Link-File (Join-Path $Win "windows-terminal.json")       "$HOME\AppData\Local\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"
if (Get-Command kanata -ErrorAction SilentlyContinue) {
    New-Item -ItemType Directory -Force -Path "$HOME\AppData\Roaming\kanata" | Out-Null
    Link-File (Join-Path $Win "kanata.kbd")               "$HOME\AppData\Roaming\kanata\kanata.kbd"
} else {
    Write-Host "note   kanata not installed; skipping (see Windows Setup.md)"
}

Write-Host "`n== shared configs =="
Link-File (Join-Path $Shared "nvim")       "$HOME\AppData\Local\nvim"
Link-File (Join-Path $Shared "opencode")   "$HOME\.config\opencode"
Link-File (Join-Path $Shared "codex")      "$HOME\.codex"
Link-File (Join-Path $Shared "gemini")     "$HOME\.gemini"
Link-File (Join-Path $Shared "agents")     "$HOME\.agents"

Write-Host "`nDone."