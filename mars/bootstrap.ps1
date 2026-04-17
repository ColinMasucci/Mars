# ─────────────────────────────────────────────
#  MARS Language Bootstrap Installer  (Windows)
# ─────────────────────────────────────────────
#
#  One-liner install (PowerShell):
#
#    powershell -c "iex (iwr -useb https://raw.githubusercontent.com/reillydesai/Mars-test/venv-fix/mars/bootstrap.ps1).Content"
#
#  NOTE: Do NOT use "iwr ... | iex" -- that breaks interactive prompts.
#        The form above downloads the entire script first, then executes it.
#

$ErrorActionPreference = "Stop"

# ── Guard: detect non-interactive session ────
if (-not [Environment]::UserInteractive) {
    Write-Host ""
    Write-Host "  Error: This installer requires an interactive terminal."
    Write-Host ""
    Write-Host "  Please use this form:"
    Write-Host ""
    Write-Host '    powershell -c "iex (iwr -useb https://github.com/ColinMasucci/Mars/mars/bootstrap.ps1).Content"'
    Write-Host ""
    exit 1
}

$RepoUrl   = "https://github.com/ColinMasucci/Mars.git"
$Branch    = "venv-fix"
$MarsHome  = Join-Path $HOME ".mars"
$RepoSubdir = "mars"

Write-Host ""
Write-Host "  +=======================================+"
Write-Host "  |   MARS Language Bootstrap Installer   |"
Write-Host "  +=======================================+"
Write-Host ""

# ── Check prerequisites ──────────────────────
foreach ($cmd in @("git", "python")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host "  Error: '$cmd' is required but not found. Please install it first."
        exit 1
    }
}

# ── Select mode ──────────────────────────────
Write-Host "  Select installation mode:"
Write-Host ""
Write-Host "    1) User      - Install Mars as a standalone tool"
Write-Host "                   Installs to ~/.mars, no source code kept"
Write-Host ""
Write-Host "    2) Developer - Clone the repo and create an editable install"
Write-Host "                   Source stays in .\Mars-test, edits take effect immediately"
Write-Host ""

$choice = Read-Host "  Enter choice [1/2]"
Write-Host ""

switch ($choice) {
    "1" { $Mode = "user" }
    "2" { $Mode = "dev"  }
    default {
        Write-Host "  Invalid choice. Exiting."
        exit 1
    }
}

# ══════════════════════════════════════════════
#  USER MODE
# ══════════════════════════════════════════════
if ($Mode -eq "user") {

    Write-Host "  Cloning Mars repository (this may take a moment) ..."
    $TmpDir = Join-Path ([System.IO.Path]::GetTempPath()) "mars-install-$(Get-Random)"
    git clone --depth 1 --branch $Branch $RepoUrl $TmpDir --quiet

    $SourceDir = Join-Path $TmpDir $RepoSubdir

    try {
        & (Join-Path $SourceDir "install.ps1") -Mode user -VenvDir $MarsHome
    } finally {
        Write-Host "  Cleaning up temporary files ..."
        Remove-Item -Recurse -Force $TmpDir -ErrorAction SilentlyContinue
    }

    Write-Host ""
    Write-Host "  Mars is installed at: $MarsHome"
    Write-Host ""

# ══════════════════════════════════════════════
#  DEVELOPER MODE
# ══════════════════════════════════════════════
} else {

    $CloneDir = Join-Path (Get-Location) "Mars-test"

    if (Test-Path $CloneDir) {
        Write-Host "  Directory .\Mars-test already exists."
        $useExisting = Read-Host "  Use existing checkout? [y/N]"
        if ($useExisting -notmatch "^[Yy]$") {
            Write-Host "  Exiting. Remove or rename the directory and try again."
            exit 1
        }
    } else {
        Write-Host "  Cloning Mars repository ..."
        git clone --branch $Branch $RepoUrl $CloneDir --quiet
    }

    $SourceDir = Join-Path $CloneDir $RepoSubdir

    & (Join-Path $SourceDir "install.ps1") -Mode dev

    Write-Host ""
    Write-Host "  Source code is at: $SourceDir"

}
