# ─────────────────────────────────────────────
#  MARS Language Installer  (Windows / PowerShell)
# ─────────────────────────────────────────────
#
#  Can be run interactively or driven by parameters:
#    .\install.ps1                                (interactive)
#    .\install.ps1 -Mode user                     (non-interactive)
#    .\install.ps1 -Mode dev -VenvDir "$HOME\.mars"
#

param(
    [string]$Mode = "",
    [string]$VenvDir = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# ── Interactive prompt if no -Mode given ─────
if ($Mode -eq "") {
    Write-Host ""
    Write-Host "  MARS Language Installer"
    Write-Host "  -------------------------------------"
    Write-Host ""
    Write-Host "  Select installation mode:"
    Write-Host ""
    Write-Host "    1) User      - Install Mars as a standalone tool (stable, no link to source)"
    Write-Host "    2) Developer - Editable install linked to this source tree"
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
}

# ── Resolve venv path ────────────────────────
if ($VenvDir -eq "") {
    $VenvDir = Join-Path $ScriptDir ".venv"
}

# ── Create virtual environment ───────────────
if (-not (Test-Path $VenvDir)) {
    Write-Host "  Creating virtual environment at $VenvDir ..."
    python -m venv $VenvDir
} else {
    Write-Host "  Virtual environment already exists at $VenvDir"
}

# ── Activate and install ─────────────────────
$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
& $ActivateScript

Write-Host "  Upgrading pip ..."
pip install --upgrade pip --quiet

if ($Mode -eq "user") {
    Write-Host "  Installing Mars (user mode) ..."
    pip install $ScriptDir --quiet
} else {
    Write-Host "  Installing Mars (developer mode with dev extras) ..."
    pip install -e "$ScriptDir[dev]" --quiet
}

Write-Host ""
Write-Host "  -------------------------------------"
Write-Host "  Installation complete!"
Write-Host ""

# ── PATH instructions ────────────────────────
$MarsBin = Join-Path $VenvDir "Scripts"

Write-Host "  To use the 'mars' command, activate the virtual environment:"
Write-Host ""
Write-Host "    & `"$ActivateScript`""
Write-Host ""
Write-Host "  Or add the following directory to your system PATH:"
Write-Host ""
Write-Host "    $MarsBin"
Write-Host ""

if ($Mode -eq "dev") {
    Write-Host "  Developer mode: edits to source files take effect immediately."
    Write-Host "  Dev tools installed: pytest, ruff"
    Write-Host ""
}

Write-Host "  Verify installation:  mars --version"
Write-Host ""
