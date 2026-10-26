[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "This setup script is for Windows."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
    throw "Could not find pyproject.toml. Run this from a complete SiegeSense AI source checkout."
}

$PythonLauncher = Get-Command "py" -ErrorAction SilentlyContinue
if ($null -eq $PythonLauncher) {
    throw "Python Launcher py.exe was not found. Install Python 3.12 for Windows from python.org, including the Python Launcher, then open a new PowerShell window."
}

$LauncherVersion = & $PythonLauncher.Source -3.12 --version 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.12 was not found through py -3.12. Install Python 3.12 for Windows, then rerun this script."
}
Write-Host "Using $LauncherVersion"

$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    if (Test-Path $VenvDir) {
        throw "The .venv folder exists but has no usable Python executable. Rename or remove .venv after preserving anything important, then rerun setup."
    }

    & $PythonLauncher.Source -3.12 -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the virtual environment. Confirm Python 3.12 is installed and retry."
    }
}

$VenvVersion = (& $VenvPython --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $VenvVersion -notmatch "^Python 3\.12\.") {
    throw "The existing .venv is not using Python 3.12 ($VenvVersion). Rename or remove .venv after preserving anything important, then rerun setup."
}

Push-Location $RepoRoot
try {
    Write-Host "Updating pip..."
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed with exit code $LASTEXITCODE."
    }

    Write-Host "Installing SiegeSense AI, developer checks, and local video-analysis dependencies..."
    & $VenvPython -m pip install -e ".[dev,vision]"
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed. Check the pip error above and your internet connection, then rerun setup."
    }
}
finally {
    Pop-Location
}

Write-Host "Setup complete."
Write-Host "Launch the app with: .\scripts\run_windows.ps1"
Write-Host "Run local checks with: .\scripts\check_windows.ps1"
