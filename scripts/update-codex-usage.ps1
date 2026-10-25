param(
    [string]$Python,
    [string]$Codex
)

$ErrorActionPreference = 'Stop'
if (-not $Python) {
    $taskBundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $taskBundledPython) {
        $Python = $taskBundledPython
    } else {
        $Python = 'python'
    }
}

$taskExportArguments = @((Join-Path $PSScriptRoot 'sync-codex-usage.py'))
if ($Codex) { $taskExportArguments += @('--codex', $Codex) }
& $Python @taskExportArguments
if ($LASTEXITCODE -ne 0) { throw 'Codex usage export failed; existing profile assets were preserved.' }

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & $Python (Join-Path $PSScriptRoot 'generate-profile.py')
    if ($LASTEXITCODE -ne 0) { throw 'Profile generation failed. The exported token snapshot remains available.' }
} finally {
    Pop-Location
}
