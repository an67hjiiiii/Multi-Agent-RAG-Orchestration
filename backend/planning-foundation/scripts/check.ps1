param([string]$PythonBin)
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonBin) {
    $venvPython = Join-Path $packageRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) {
        $PythonBin = $venvPython
    } else {
        $PythonBin = 'python'
    }
}
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $packageRoot 'src'
Push-Location -LiteralPath $packageRoot
try {
    & $PythonBin -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Contract tests failed.' }
    & $PythonBin examples/demo.py
    if ($LASTEXITCODE -ne 0) { throw 'Offline demo failed.' }
} finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
