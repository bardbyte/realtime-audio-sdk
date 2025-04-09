Write-Host "Checking Python version..."
python --version
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python is required."
    exit
}

Write-Host "Creating virtual environment..."
python -m venv venv

Write-Host "Activating virtual environment..."
.\venv\Scripts\Activate.ps1

Write-Host "Installing dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

Write-Host "Installing realtime-audio-sdk in editable mode..."
pip install -e .

Write-Host "SDK setup complete. Virtual environment is activated."
