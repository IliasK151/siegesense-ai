[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$SetupScript = Join-Path $PSScriptRoot "setup_windows.ps1"
$CheckScript = Join-Path $PSScriptRoot "check_windows.ps1"

& $SetupScript
& $CheckScript

Push-Location $RepoRoot
try {
    Write-Host "Installing the Windows packager..."
    & $VenvPython -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller installation failed with exit code $LASTEXITCODE."
    }

    Write-Host "Building the preview application..."
    $PyInstallerArgs = @(
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name", "SiegeSenseAI",
        "--paths", "src",
        "--collect-submodules", "siegesense",
        "--collect-all", "PySide6.QtMultimedia",
        "--collect-all", "PySide6.QtMultimediaWidgets",
        "main.py"
    )
    & $VenvPython -m PyInstaller @PyInstallerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }

    $PackageDir = Join-Path $RepoRoot "dist\SiegeSenseAI"
    $Executable = Join-Path $PackageDir "SiegeSenseAI.exe"
    if (-not (Test-Path $Executable)) {
        throw "The package executable was not created at $Executable."
    }

    $PreviousQtPlatform = $env:QT_QPA_PLATFORM
    $PreviousLocalAppData = $env:LOCALAPPDATA
    $PreviousSmokeLog = $env:SIEGESENSE_SMOKE_LOG
    $SmokeData = Join-Path ([System.IO.Path]::GetTempPath()) ("SiegeSenseSmoke-" + [guid]::NewGuid().ToString("N"))
    $SmokeLog = Join-Path ([System.IO.Path]::GetTempPath()) ("SiegeSenseSmoke-" + [guid]::NewGuid().ToString("N") + ".txt")
    New-Item -ItemType Directory -Path $SmokeData -Force | Out-Null

    try {
        $env:QT_QPA_PLATFORM = "offscreen"
        $env:LOCALAPPDATA = $SmokeData
        $env:SIEGESENSE_SMOKE_LOG = $SmokeLog

        Write-Host "Smoke-testing the packaged executable..."
        $Process = Start-Process -FilePath $Executable -ArgumentList "--smoke-test" -Wait -PassThru
        if ($Process.ExitCode -ne 0) {
            if (Test-Path $SmokeLog) {
                Get-Content $SmokeLog
            }
            throw "Packaged-app smoke test failed with exit code $($Process.ExitCode)."
        }
    }
    finally {
        if ($null -eq $PreviousQtPlatform) {
            Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        }
        else {
            $env:QT_QPA_PLATFORM = $PreviousQtPlatform
        }
        if ($null -eq $PreviousLocalAppData) {
            Remove-Item Env:LOCALAPPDATA -ErrorAction SilentlyContinue
        }
        else {
            $env:LOCALAPPDATA = $PreviousLocalAppData
        }
        if ($null -eq $PreviousSmokeLog) {
            Remove-Item Env:SIEGESENSE_SMOKE_LOG -ErrorAction SilentlyContinue
        }
        else {
            $env:SIEGESENSE_SMOKE_LOG = $PreviousSmokeLog
        }
        Remove-Item $SmokeData -Recurse -Force -ErrorAction SilentlyContinue
    }

    Copy-Item (Join-Path $RepoRoot "README.md") (Join-Path $PackageDir "README.md") -Force
    $DocsDir = Join-Path $PackageDir "docs"
    New-Item -ItemType Directory -Path $DocsDir -Force | Out-Null
    Copy-Item (Join-Path $RepoRoot "docs\ANNOTATION_GUIDE.md") $DocsDir -Force
    Copy-Item (Join-Path $RepoRoot "docs\ANALYSIS_VALIDATION_PLAN.md") $DocsDir -Force

    $ArchivePath = Join-Path $RepoRoot "dist\SiegeSenseAI-Windows-x64.zip"
    Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ArchivePath -Force
    Write-Host "Preview package created: $ArchivePath"
    Write-Host "This is a local recording-review and manual-annotation preview, not a validated automatic aim coach."
}
finally {
    Pop-Location
}
