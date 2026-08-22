[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$forgeRoot = $PSScriptRoot
$venvRoot = Join-Path $forgeRoot '.venv'
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'

Push-Location $forgeRoot
try {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        & py -3.13 -c "import sys; assert sys.version_info >= (3, 13)"
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.13 is required.' }
        if (-not (Test-Path -LiteralPath $venvPython)) {
            & py -3.13 -m venv $venvRoot
            if ($LASTEXITCODE -ne 0) { throw 'Failed to create .venv.' }
        }
    } else {
        $pythonCommand = Get-Command python -ErrorAction Stop
        & $pythonCommand.Source -c "import sys; assert sys.version_info >= (3, 13)"
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.13 is required.' }
        if (-not (Test-Path -LiteralPath $venvPython)) {
            & $pythonCommand.Source -m venv $venvRoot
            if ($LASTEXITCODE -ne 0) { throw 'Failed to create .venv.' }
        }
    }
    & $venvPython -c "import sys; assert sys.version_info >= (3, 13)"
    if ($LASTEXITCODE -ne 0) { throw 'Existing .venv is not Python 3.13; recreate it.' }
    & $venvPython -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & $venvPython forge.py doctor --report evidence\setup-doctor.json
    if ($LASTEXITCODE -ne 0) { throw 'PTCG Strategy Forge doctor failed.' }
} finally {
    Pop-Location
}
