[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ForgeArguments
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$forgeRoot = $PSScriptRoot
$venvPython = Join-Path $forgeRoot '.venv\Scripts\python.exe'
$pythonPath = $venvPython
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = (Get-Command python -ErrorAction Stop).Source
}

Push-Location $forgeRoot
try {
    & $pythonPath forge.py @ForgeArguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
