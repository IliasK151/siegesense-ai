[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $AppArguments
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$EntryPoint = Join-Path $RepoRoot "main.py"

if (-not (Test-Path $VenvPython)) {
    throw "The SiegeSense AI environment is missing. Run the setup_windows.ps1 script first."
}
if (-not (Test-Path $EntryPoint)) {
    throw "main.py was not found. Ensure this is the project root."
}

Push-Location $RepoRoot
try {
    & $VenvPython $EntryPoint @AppArguments
    if ($LASTEXITCODE -ne 0) {
        throw "SiegeSense AI exited with code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
