param(
    [switch]$ResetVenv
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host '=== Unum Sunt Sprite Studio - Source Runner ==='
Write-Host 'Supported source runtime: Python 3.13.x or 3.14.x (x64)'
Write-Host 'Note: the Python 3.13 lock applies only to the official standalone build.'
Write-Host ''

function Test-SourcePython([string]$InterpreterPath) {
    if ([string]::IsNullOrWhiteSpace($InterpreterPath) -or -not (Test-Path $InterpreterPath)) {
        return $false
    }
    try {
        $probe = & $InterpreterPath -c "import struct,sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor)+'|'+str(struct.calcsize('P')*8)+'|'+sys.executable)" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $probe) { return $false }
        $parts = ($probe | Select-Object -Last 1).Trim().Split('|')
        return ($parts.Length -ge 2 -and @('3.13','3.14') -contains $parts[0] -and $parts[1] -eq '64')
    }
    catch { return $false }
}

function Resolve-SourcePython {
    # Prefer the user's current/default Python when it is already compatible.
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd -and (Test-SourcePython $pythonCmd.Source)) {
        return $pythonCmd.Source
    }

    # Then try explicitly installed 3.14/3.13 runtimes through either launcher.
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($tag in @('3.14','3.13')) {
            try {
                $candidate = & $py.Source "-$tag" -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $candidate) {
                    $path = ($candidate | Select-Object -Last 1).Trim()
                    if (Test-SourcePython $path) { return $path }
                }
            }
            catch { }
        }
    }

    $manager = Get-Command pymanager -ErrorAction SilentlyContinue
    if ($manager) {
        foreach ($tag in @('3.14','3.13')) {
            try {
                $candidate = & $manager.Source list --one --format=exe $tag 2>$null
                if ($LASTEXITCODE -eq 0 -and $candidate) {
                    $path = ($candidate | Select-Object -Last 1).Trim()
                    if (Test-SourcePython $path) { return $path }
                }
            }
            catch { }
        }
    }
    return $null
}

$venv = Join-Path $PSScriptRoot '.venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'

if ($ResetVenv -and (Test-Path $venv)) {
    Write-Host 'Reset requested: removing .venv...'
    Remove-Item -Recurse -Force $venv
}

if (Test-Path $venvPython) {
    if (-not (Test-SourcePython $venvPython)) {
        Write-Host '.venv uses an unsupported or corrupted Python runtime: recreating...' -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venv
    }
}

if (-not (Test-Path $venvPython)) {
    $basePython = Resolve-SourcePython
    if (-not $basePython) {
        throw 'No compatible x64 Python runtime was found. Install Python 3.13 or 3.14 to run from source. For the official build, use build_windows_standalone.bat, which manages Python 3.13 separately.'
    }
    Write-Host "Creating .venv with: $basePython"
    & $basePython -m venv $venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
        throw 'Failed to create the .venv environment.'
    }
}

Write-Host "Source runtime: $(& $venvPython --version 2>&1)"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Requirements installation failed.' }

& $venvPython main.py
exit $LASTEXITCODE
