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