param(
    [switch]$SkipTests,
    [switch]$InstallPython313,
    [switch]$NoPythonInstallPrompt,
    [switch]$ResetBuildVenv
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$BuildPythonMajor = 3
$BuildPythonMinor = 13
$BuildPythonTag = '3.13'
$BuildPythonLabel = 'Python 3.13 x64'

Write-Host '=== Unum Sunt Sprite Studio R5c6 - Windows Standalone Core ==='
Write-Host "Build runtime ufficiale: $BuildPythonLabel"
Write-Host ''

if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'R5c6 supporta esclusivamente Windows x64.'
}

function Test-BuildPython([string]$InterpreterPath) {
    if ([string]::IsNullOrWhiteSpace($InterpreterPath) -or -not (Test-Path $InterpreterPath)) {
        return $false
    }
    try {
        $probe = & $InterpreterPath -c "import struct,sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor)+'|'+str(struct.calcsize('P')*8)+'|'+sys.executable)" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $probe) { return $false }
        $parts = ($probe | Select-Object -Last 1).Trim().Split('|')
        return ($parts.Length -ge 2 -and $parts[0] -eq '3.13' -and $parts[1] -eq '64')
    }
    catch {
        return $false
    }
}

function Get-Python313Path {
    # 1) Legacy launcher or new Python Install Manager compatibility launcher.
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $candidate = & $py.Source -3.13-64 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $candidate) {
                $path = ($candidate | Select-Object -Last 1).Trim()
                if (Test-BuildPython $path) { return $path }
            }
        }
        catch { }
    }

    # 2) Explicit runtime alias, when available.
    $alias = Get-Command python3.13.exe -ErrorAction SilentlyContinue
    if ($alias -and (Test-BuildPython $alias.Source)) {
        return $alias.Source
    }

    # 3) Common python.org install locations, useful when no launcher/alias is available.
    $commonCandidates = @()
    if ($env:LOCALAPPDATA) { $commonCandidates += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe') }
    if ($env:ProgramFiles) { $commonCandidates += (Join-Path $env:ProgramFiles 'Python313\python.exe') }
    foreach ($candidate in $commonCandidates) {
        if (Test-BuildPython $candidate) { return $candidate }
    }

    # 4) Python Install Manager. Scripted installs should prefer the
    #    unambiguous pymanager command when a legacy py.exe is also present.
    $manager = Get-PythonManagerPath
    if ($manager) {
        try {
            $candidate = & $manager list --one --format=exe $BuildPythonTag 2>$null
            if ($LASTEXITCODE -eq 0 -and $candidate) {
                $path = ($candidate | Select-Object -Last 1).Trim()
                if (Test-BuildPython $path) { return $path }
            }
        }
        catch { }
        try {
            $candidate = & $manager exec -V:3.13 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $candidate) {
                $path = ($candidate | Select-Object -Last 1).Trim()
                if (Test-BuildPython $path) { return $path }
            }
        }
        catch { }
    }

    return $null
}

function Get-PythonManagerPath {
    $manager = Get-Command pymanager -ErrorAction SilentlyContinue
    if ($manager) { return $manager.Source }

    # App execution aliases normally live here. This fallback also helps when
    # WinGet has just installed the manager in the current PowerShell session.
    if ($env:LOCALAPPDATA) {
        $windowsApps = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'
        $direct = Join-Path $windowsApps 'pymanager.exe'
        if (Test-Path $direct) { return $direct }

        $packageDirs = @(
            'PythonSoftwareFoundation.PythonManager_3847v3x7pw1km',
            'PythonSoftwareFoundation.PythonManager_qbz5n2kfra8p0'
        )
        foreach ($dir in $packageDirs) {
            $candidate = Join-Path (Join-Path $windowsApps $dir) 'pymanager.exe'
            if (Test-Path $candidate) { return $candidate }
        }
    }
    return $null
}

function Confirm-PythonInstall {
    if ($InstallPython313) { return $true }
    if ($NoPythonInstallPrompt) { return $false }

    Write-Host ''
    Write-Host "$BuildPythonLabel non e' disponibile sul sistema." -ForegroundColor Yellow
    Write-Host 'Python 3.14 o altre versioni gia presenti NON verranno modificate.'
    $answer = Read-Host 'Installare automaticamente Python 3.13 x64 per la build? [S/N]'
    return @('s', 'si', 'sì', 'y', 'yes') -contains $answer.Trim().ToLowerInvariant()
}

function Ensure-PythonManager {
    $manager = Get-PythonManagerPath
    if ($manager) { return $manager }

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'Python Install Manager non trovato e WinGet non disponibile. Installare Python 3.13 x64 manualmente e rilanciare la build.'
    }

    Write-Host 'Installazione Python Install Manager tramite WinGet...'
    & $winget.Source install 9NQ7512CXL7T -e --accept-package-agreements --accept-source-agreements --disable-interactivity | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw 'Installazione del Python Install Manager tramite WinGet fallita.'
    }

    # Give Windows app aliases a moment to become visible, then probe again.
    Start-Sleep -Seconds 2
    $manager = Get-PythonManagerPath
    if (-not $manager) {
        throw 'Python Install Manager installato, ma il comando pymanager non e ancora disponibile. Chiudere e rilanciare build_windows_standalone.bat.'
    }
    return $manager
}

function Install-Python313Runtime {
    if (-not (Confirm-PythonInstall)) {
        throw "$BuildPythonLabel necessario per la build ufficiale. Installazione annullata."
    }

    $manager = Ensure-PythonManager
    Write-Host "Installazione $BuildPythonLabel tramite Python Install Manager..."
    & $manager install $BuildPythonTag | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Installazione di $BuildPythonLabel fallita."
    }
    try { & $manager install --refresh | Out-Null } catch { }
    Start-Sleep -Seconds 1

    $resolved = Get-Python313Path
    if (-not $resolved) {
        throw "$BuildPythonLabel risulta installato ma non e stato possibile risolvere il percorso dell'interprete."
    }
    return $resolved
}

$venv = Join-Path $PSScriptRoot '.build-venv'
$python = Join-Path $venv 'Scripts\python.exe'

if ($ResetBuildVenv -and (Test-Path $venv)) {
    Write-Host 'Reset richiesto: rimozione .build-venv...'
    Remove-Item -Recurse -Force $venv
}

if (Test-Path $python) {
    if (Test-BuildPython $python) {
        Write-Host "Ambiente build esistente valido: $(& $python --version 2>&1)"
    }
    else {
        Write-Host '.build-venv usa una versione Python non compatibile o e corrotto: ricreazione automatica...' -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venv
    }
}

if (-not (Test-Path $python)) {
    $basePython = Get-Python313Path
    if (-not $basePython) {
        $basePython = Install-Python313Runtime
    }

    if (-not (Test-BuildPython $basePython)) {
        throw "Interprete risolto non conforme al contratto ${BuildPythonLabel}: $basePython"
    }

    Write-Host "Creazione ambiente build con: $basePython"
    & $basePython -m venv $venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $python)) {
        throw 'Creazione .build-venv fallita.'
    }
}

if (-not (Test-BuildPython $python)) {
    throw '.build-venv non soddisfa il contratto Python 3.13 x64.'
}

Write-Host "Runtime build attivo: $(& $python --version 2>&1)"
Write-Host "Interprete build: $python"
Write-Host ''

& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Aggiornamento pip fallito.' }
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Installazione requirements-build fallita.' }

if (-not $SkipTests) {
    Write-Host 'Esecuzione regressione automatica...'
    & $python -m unittest discover -s tests -p 'test_*.py'
    if ($LASTEXITCODE -ne 0) { throw 'Test automatici falliti. Build interrotta.' }
}

Remove-Item -Recurse -Force build\pyinstaller -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist\UnumSuntSpriteStudio -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force build\pyinstaller | Out-Null

Write-Host 'Build PyInstaller onedir...'
& $python -m PyInstaller --noconfirm --clean --workpath build\pyinstaller UnumSuntSpriteStudio.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller ha restituito un errore.' }

$distDir = Join-Path $PSScriptRoot 'dist\UnumSuntSpriteStudio'
$exe = Join-Path $distDir 'UnumSuntSpriteStudio.exe'
if (-not (Test-Path $exe)) { throw 'EXE standalone non trovato dopo PyInstaller.' }

$selfCheck = Join-Path $distDir 'standalone_selfcheck.json'
Write-Host 'Self-check del binario congelato...'
Remove-Item -Force $selfCheck -ErrorAction SilentlyContinue

$selfCheckArgs = @('--self-check', ('"{0}"' -f $selfCheck))
$selfCheckProcess = Start-Process -FilePath $exe -ArgumentList $selfCheckArgs -Wait -PassThru
if ($selfCheckProcess.ExitCode -ne 0) {
    throw "Self-check del binario standalone fallito (exit code $($selfCheckProcess.ExitCode))."
}
if (-not (Test-Path $selfCheck)) { throw 'Il self-check non ha prodotto il report JSON.' }
$check = Get-Content $selfCheck -Raw | ConvertFrom-Json
if ($check.status -ne 'passed' -or -not $check.frozen) { throw 'Self-check non valido: il runtime congelato non risulta READY.' }

& $python tools\write_release_manifest.py $distDir (Join-Path $distDir 'RELEASE_MANIFEST_R5c6.json')
if ($LASTEXITCODE -ne 0) { throw 'Impossibile generare il release manifest.' }

$releaseDir = Join-Path $PSScriptRoot 'release'
New-Item -ItemType Directory -Force $releaseDir | Out-Null
$zipPath = Join-Path $releaseDir 'UnumSunt_Sprite_Studio_R5c6_Windows_x64_Standalone.zip'
$hashPath = Join-Path $releaseDir 'UnumSunt_Sprite_Studio_R5c6_Windows_x64_Standalone_SHA256.txt'
Remove-Item -Force $zipPath, $hashPath -ErrorAction SilentlyContinue

Write-Host 'Creazione archivio release...'
Compress-Archive -Path $distDir -DestinationPath $zipPath -CompressionLevel Optimal
$hash = (Get-FileHash -Algorithm SHA256 $zipPath).Hash.ToLowerInvariant()
"$hash  $(Split-Path $zipPath -Leaf)" | Set-Content -Encoding ascii $hashPath

Write-Host ''
Write-Host 'BUILD COMPLETATA'
Write-Host "Standalone: $distDir"
Write-Host "Release ZIP: $zipPath"
Write-Host "SHA-256: $hash"
Write-Host 'Il PC destinatario NON richiede Python. Python 3.13 serve soltanto alla pipeline di build.'
Write-Host 'Il runtime AI resta esterno al bundle Core ed è gestito dal Runtime Manager R5c6.'
