Write-Host "Creating virtual environment..."
python -m venv .venv

Write-Host "Activating virtual environment..."
.venv\Scripts\Activate.ps1

Write-Host "Upgrading pip..."
python -m pip install --upgrade pip

Write-Host "Installing MARS package..."
pip install -e .

Write-Host ""
Write-Host "MARS installed successfully!"
Write-Host ""
Write-Host "To activate later, run:"
Write-Host "  .venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "To run MARS:"
Write-Host "  mars run test_file.mars"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$vsixPath = Join-Path $scriptDir "mars-extension-1.0.4.vsix"

#Check for VSCode
$codePath = "$env:LOCALAPPDATA\Programs\Microsoft VS Code\bin\code.cmd"

if (-not (Test-Path $codePath)) {
    $codePath = "$env:ProgramFiles\Microsoft VS Code\bin\code.cmd"
}

if (-not (Test-Path $codePath)) {
    Write-Error "Visual Studio Code was not found. Please install VS Code and re-run this installer."
    exit 1
}

#Check for .vsix
if (-not (Test-Path $vsixPath)) {
    Write-Error "Extension file not found: $vsixPath"
    exit 1
}

#Install the extension
Write-Host "Installing VS Code extension..."
& $codePath --install-extension $vsixPath --force

if ($LASTEXITCODE -eq 0) {
    Write-Host "Extension installed successfully."
} else {
    Write-Error "Extension installation failed with exit code $LASTEXITCODE."
    exit 1
}
