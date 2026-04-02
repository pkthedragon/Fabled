[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Version = "1.0.0",

    [switch]$RebuildExe
)

$ErrorActionPreference = "Stop"

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version must use Windows Installer's three-part numeric format, for example 1.0.0."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sourceExe = Join-Path $repoRoot "Fabled.exe"
$wxsPath = Join-Path $PSScriptRoot "Fabled.Installer.wxs"
$artifactsDir = Join-Path $PSScriptRoot "artifacts"
$outputPath = Join-Path $artifactsDir "Fabled-$Version-x64.msi"

if ($RebuildExe) {
    Push-Location $repoRoot
    try {
        pyinstaller --noconfirm --clean --onefile --windowed --name Fabled --distpath . main.py
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path $sourceExe)) {
    throw "Fabled.exe was not found at $sourceExe. Build the game executable first or pass -RebuildExe."
}

$wixCandidates = @(
    (Join-Path ${env:ProgramFiles} "WiX Toolset v6.0\bin\wix.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "WiX Toolset v6.0\bin\wix.exe")
)

$wixExe = $null
foreach ($candidate in $wixCandidates) {
    if ($candidate -and (Test-Path $candidate)) {
        $wixExe = $candidate
        break
    }
}

if (-not $wixExe) {
    $wixCommand = Get-Command wix -ErrorAction SilentlyContinue
    if ($wixCommand) {
        $wixExe = $wixCommand.Source
    }
}

if (-not $wixExe) {
    throw "WiX CLI was not found. Install WiX Toolset CLI 6.x and rerun this script."
}

New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null
Remove-Item $outputPath -Force -ErrorAction SilentlyContinue

& $wixExe build $wxsPath `
    -arch x64 `
    -d "ProductVersion=$Version" `
    -d "SourceExe=$sourceExe" `
    -o $outputPath

if ($LASTEXITCODE -ne 0) {
    throw "WiX build failed."
}

Get-Item $outputPath | Select-Object FullName, Length, LastWriteTime
