# Windows PowerShell setup for AI-Based Online Exam Proctoring System
# Notes:
# - Avoids && chaining (your environment rejects it)
# - Creates/uses a virtual environment
# - Installs wheel-based dependencies only (no Visual C++ Build Tools needed)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Project root: $ProjectRoot"

# Python version guard removed so setup can run on Python 3.14 too.
# Face verification now supports OpenCV fallback when MediaPipe is unavailable.

# 1) Create venv (idempotent)
if (-not (Test-Path "$ProjectRoot\venv")) {
  Write-Host "Creating venv..."
  python -m venv "$ProjectRoot\venv"
}

# 2) Activate venv
$venvScripts = "$ProjectRoot\venv\Scripts\"
$activate = Join-Path $venvScripts 'Activate.ps1'
if (-not (Test-Path $activate)) {
  throw "Could not find venv Activate.ps1 at: $activate"
}

Write-Host "Activating venv..."
& $activate

# 3) Upgrade pip tooling
Write-Host "Upgrading pip, setuptools, wheel..."
python -m pip install --upgrade pip setuptools wheel

# 4) Install requirements
Write-Host "Installing requirements..."
python -m pip install -r "$ProjectRoot\requirements.txt"

Write-Host "Done. Running import tests..."
python -c "import cv2; import mediapipe; print('import cv2 + mediapipe: OK')"

