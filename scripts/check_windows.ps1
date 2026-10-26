[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    throw "The SiegeSense AI environment is missing. Run the setup_windows.ps1 script first."
}

$PreviousQtPlatform = $env:QT_QPA_PLATFORM
Push-Location $RepoRoot
try {
    $env:QT_QPA_PLATFORM = "offscreen"

    Write-Host "Running the test suite..."
    & $VenvPython -m pytest
    if ($LASTEXITCODE -ne 0) {
        throw "pytest failed with exit code $LASTEXITCODE."
    }

    Write-Host "Running Ruff lint checks..."
    & $VenvPython -m ruff check .
    if ($LASTEXITCODE -ne 0) {
        throw "Ruff failed with exit code $LASTEXITCODE."
    }
}
finally {
    if ($null -eq $PreviousQtPlatform) {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    }
    else {
        $env:QT_QPA_PLATFORM = $PreviousQtPlatform
    }
    Pop-Location
}

Write-Host "Tests and lint checks passed locally."
