Write-Host "======================================="
Write-Host "   MARS Language Installer"
Write-Host "======================================="

# -----------------------------
# CONFIG
# -----------------------------
$repoUrl = "https://github.com/ColinMasucci/Mars.git"
$venvDir = ".venv"
$repoClone = Join-Path $PWD "Mars"

# -----------------------------
# STEP 1: Create virtual environment
# -----------------------------
if (-Not (Test-Path $venvDir)) {
    Write-Host "Creating virtual environment..."
    python -m venv $venvDir

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment."
        exit 1
    }
} else {
    Write-Host "Virtual environment already exists. Skipping..."
}

# Resolve venv python explicitly (NO activation needed)
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-Not (Test-Path $venvPython)) {
    Write-Error "Virtual environment python not found at $venvPython"
    exit 1
}

# -----------------------------
# STEP 2: Clone repository (for VSIX + source install)
# -----------------------------
if (-Not (Test-Path $repoClone)) {
    Write-Host "Cloning MARS repository..."
    git clone $repoUrl $repoClone

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to clone MARS repository."
        exit 1
    }
} else {
    Write-Host "Repository already cloned. Skipping..."
}

# -----------------------------
# STEP 3: Upgrade pip (inside venv)
# -----------------------------
Write-Host "Upgrading pip..."
& $venvPython -m pip install --upgrade pip

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to upgrade pip."
    exit 1
}

# -----------------------------
# STEP 4: Install MARS (from local clone)
# -----------------------------
Write-Host "Installing MARS from local repository..."
& $venvPython -m pip install $repoClone

if ($LASTEXITCODE -ne 0) {
    Write-Error "MARS installation failed."
    exit 1
}

# -----------------------------
# STEP 5: Verify CLI installation
# -----------------------------
Write-Host "Verifying installation..."

try {
    & $venvPython -m mars.mars_lang.cli --help | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "MARS CLI verified successfully."
    } else {
        Write-Warning "MARS installed but CLI verification failed."
    }
}
catch {
    Write-Warning "Could not verify MARS CLI installation."
}

# -----------------------------
# STEP 6: Find VS Code extension
# -----------------------------
Write-Host "Searching for VS Code extension..."

$vsixPath = Get-ChildItem -Path $repoClone -Recurse -Filter "*.vsix" -ErrorAction SilentlyContinue |
            Select-Object -First 1

if ($vsixPath) {
    $vsixPath = $vsixPath.FullName
    Write-Host "Found VSIX: $vsixPath"
} else {
    Write-Warning "No VSIX found. Skipping extension install."
}

# -----------------------------
# STEP 7: Locate VS Code
# -----------------------------
$codePath = "$env:LOCALAPPDATA\Programs\Microsoft VS Code\bin\code.cmd"

if (-Not (Test-Path $codePath)) {
    $codePath = "$env:ProgramFiles\Microsoft VS Code\bin\code.cmd"
}

if (-Not (Test-Path $codePath)) {
    Write-Warning "VS Code not found. Skipping extension install."
    $codePath = $null
}

# -----------------------------
# STEP 8: Install VS Code extension
# -----------------------------
if ($codePath -and $vsixPath) {
    Write-Host "Installing VS Code extension..."

    & $codePath --install-extension $vsixPath --force

    if ($LASTEXITCODE -eq 0) {
        Write-Host "VS Code extension installed successfully."
    } else {
        Write-Warning "Extension installation failed."
    }
} else {
    Write-Host "Skipping VS Code extension install."
}

# -----------------------------
# DONE
# -----------------------------
Write-Host ""
Write-Host "======================================="
Write-Host "MARS installation complete!"
Write-Host "======================================="
Write-Host ""
Write-Host "Next steps:"
Write-Host "  Activate manually (optional): .venv\Scripts\Activate.ps1"
Write-Host "  Run MARS: mars run demo.mars"
Write-Host ""