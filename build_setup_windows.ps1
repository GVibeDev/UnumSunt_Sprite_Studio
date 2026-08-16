param(
    [switch]$SkipTests,
    [switch]$InstallInnoSetup
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host '=== Unum Sunt Sprite Studio R5c7 - Windows Setup Bootstrapper ==='

# 1. Produce first the canonical standalone Core. The Setup never packages the
# source tree and therefore remains independent of Python on the target PC.
$standaloneArgs = @()
if ($SkipTests) { $standaloneArgs += '-SkipTests' }
& (Join-Path $PSScriptRoot 'build_windows_standalone.ps1') @standaloneArgs
if ($LASTEXITCODE -ne 0) { throw 'Build standalone fallita: Setup non creato.' }

function Resolve-IsccCandidate([string]$Candidate) {
    if ([string]::IsNullOrWhiteSpace($Candidate)) { return $null }
    try {
        $expanded = [Environment]::ExpandEnvironmentVariables($Candidate.Trim().Trim('"'))
        if (Test-Path -LiteralPath $expanded -PathType Leaf) {
            return (Resolve-Path -LiteralPath $expanded).Path
        }
    }
    catch { }
    return $null
}

function Find-IsccFromRegistry {
    # App Paths is the most direct registry contract when present.
    $appPathKeys = @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\ISCC.exe',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\App Paths\ISCC.exe',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\ISCC.exe'
    )
    foreach ($key in $appPathKeys) {
        try {
            $entry = Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue
            if ($entry) {
                $resolved = Resolve-IsccCandidate ([string]$entry.'(default)')
                if ($resolved) { return $resolved }
                if ($entry.Path) {
                    $resolved = Resolve-IsccCandidate (Join-Path ([string]$entry.Path) 'ISCC.exe')
                    if ($resolved) { return $resolved }
                }
            }
        }
        catch { }
    }

    # Inno Setup can be installed per-user or per-machine. Query all common
    # uninstall registry hives and use InstallLocation instead of assuming a
    # Program Files layout.
    $uninstallRoots = @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    foreach ($root in $uninstallRoots) {
        try {
            $entries = Get-ItemProperty -Path $root -ErrorAction SilentlyContinue | Where-Object {
                ($_.DisplayName -like 'Inno Setup*') -or
                ($_.Publisher -match 'JRSoftware|Jordan Russell')
            }
            foreach ($entry in $entries) {
                if ($entry.InstallLocation) {
                    $resolved = Resolve-IsccCandidate (Join-Path ([string]$entry.InstallLocation) 'ISCC.exe')
                    if ($resolved) { return $resolved }
                }

                # Some Inno uninstall entries omit InstallLocation but expose an
                # uninstaller path in the installation directory.
                if ($entry.UninstallString) {
                    $uninstall = [string]$entry.UninstallString
                    $uninstallerPath = $null
                    if ($uninstall -match '^\s*"([^"]+)"') {
                        $uninstallerPath = $Matches[1]
                    }
                    elseif ($uninstall -match '^\s*([^\s]+\.exe)') {
                        $uninstallerPath = $Matches[1]
                    }
                    if ($uninstallerPath) {
                        try {
                            $folder = Split-Path -Parent ([Environment]::ExpandEnvironmentVariables($uninstallerPath))
                            $resolved = Resolve-IsccCandidate (Join-Path $folder 'ISCC.exe')
                            if ($resolved) { return $resolved }
                        }
                        catch { }
                    }
                }
            }
        }
        catch { }
    }
    return $null
}

function Find-Iscc {
    # 1) Existing PATH entry.
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        $resolved = Resolve-IsccCandidate $cmd.Source
        if ($resolved) { return $resolved }
    }

    # 2) Deterministic common machine and per-user layouts.
    $candidates = @()
    if ($env:ProgramFiles) {
        $candidates += (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe')
        $candidates += (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    }
    if (${env:ProgramFiles(x86)}) {
        $candidates += (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7\ISCC.exe')
        $candidates += (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe')
    }
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe')
        $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
        $candidates += (Join-Path $env:LOCALAPPDATA 'Inno Setup 7\ISCC.exe')
        $candidates += (Join-Path $env:LOCALAPPDATA 'Inno Setup 6\ISCC.exe')
    }
    foreach ($candidate in $candidates) {
        $resolved = Resolve-IsccCandidate $candidate
        if ($resolved) { return $resolved }
    }

    # 3) Registry discovery covers custom installation directories and user scope.
    $registryMatch = Find-IsccFromRegistry
    if ($registryMatch) { return $registryMatch }

    # 4) Last bounded fallback: enumerate only Inno Setup directories below the
    # per-user Programs folder. Do NOT recurse arbitrary drives.
    if ($env:LOCALAPPDATA) {
        $programs = Join-Path $env:LOCALAPPDATA 'Programs'
        if (Test-Path -LiteralPath $programs) {
            try {
                $dirs = Get-ChildItem -LiteralPath $programs -Directory -Filter 'Inno Setup*' -ErrorAction SilentlyContinue
                foreach ($dir in $dirs) {
                    $resolved = Resolve-IsccCandidate (Join-Path $dir.FullName 'ISCC.exe')
                    if ($resolved) { return $resolved }
                }
            }
            catch { }
        }
    }
    return $null
}

function Install-InnoSetupWithWinGet {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'WinGet non disponibile. Installare Inno Setup manualmente e rilanciare build_setup_windows.bat.'
    }

    # Inno Setup 7 is the current official WinGet package. Keep the 6.x package
    # identifier as a compatibility fallback for systems/sources that do not yet
    # expose 7.x. The historical unversioned identifier is retained last.
    $packageIds = @(
        'JRSoftware.InnoSetup.7',
        'JRSoftware.InnoSetup',
        'JRSoftware.InnoSetup.6'
    )

    foreach ($packageId in $packageIds) {
        Write-Host "Tentativo Inno Setup tramite WinGet: $packageId"
        & $winget.Source install --id $packageId -e -s winget --accept-package-agreements --accept-source-agreements --silent | Out-Host
        $wingetExit = $LASTEXITCODE

        # WinGet may return a non-zero status when the matching package is
        # already installed and no upgrade is available. The filesystem/registry
        # discovery below is authoritative for this build, not the WinGet code.
        Start-Sleep -Seconds 2
        $detected = Find-Iscc
        if ($detected) {
            Write-Host "Inno Setup disponibile: $detected"
            return $detected
        }

        if ($wingetExit -ne 0) {
            Write-Host "WinGet ha restituito codice $wingetExit e ISCC.exe non e' ancora rilevabile." -ForegroundColor Yellow
        }
    }
    return $null
}

$iscc = Find-Iscc
if (-not $iscc) {
    $shouldInstall = $InstallInnoSetup
    if (-not $shouldInstall) {
        Write-Host 'Inno Setup non trovato.' -ForegroundColor Yellow
        $answer = Read-Host 'Installarlo automaticamente tramite WinGet? [S/N]'
        $shouldInstall = @('s','si','sì','y','yes') -contains $answer.Trim().ToLowerInvariant()
    }
    if (-not $shouldInstall) {
        throw 'Inno Setup richiesto per produrre Setup.exe.'
    }

    Write-Host 'Installazione/rilevamento Inno Setup tramite WinGet...'
    $iscc = Install-InnoSetupWithWinGet
    if (-not $iscc) {
        throw 'Inno Setup non disponibile dopo i tentativi WinGet. Installarlo manualmente oppure indicare una normale installazione contenente ISCC.exe e rilanciare la build.'
    }
}

Write-Host "Compiler installer: $iscc"
$installerScript = Join-Path $PSScriptRoot 'installer\UnumSuntSpriteStudio_R5c7.iss'
if (-not (Test-Path $installerScript)) { throw 'Script Inno Setup R5c7 non trovato.' }

$installerOut = Join-Path $PSScriptRoot 'release\installer'
New-Item -ItemType Directory -Force $installerOut | Out-Null
Remove-Item -Force (Join-Path $installerOut 'UnumSunt_Sprite_Studio_R5c7_Setup_x64.exe') -ErrorAction SilentlyContinue
Remove-Item -Force (Join-Path $installerOut 'UnumSunt_Sprite_Studio_R5c7_Setup_x64_SHA256.txt') -ErrorAction SilentlyContinue

Write-Host 'Compilazione Setup.exe...'
& $iscc /Qp $installerScript | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Compilazione Inno Setup fallita.' }

$setupExe = Join-Path $installerOut 'UnumSunt_Sprite_Studio_R5c7_Setup_x64.exe'
if (-not (Test-Path $setupExe)) { throw 'Setup.exe non trovato dopo la compilazione.' }

$hash = (Get-FileHash -Algorithm SHA256 $setupExe).Hash.ToLowerInvariant()
$hashFile = Join-Path $installerOut 'UnumSunt_Sprite_Studio_R5c7_Setup_x64_SHA256.txt'
"$hash  $(Split-Path $setupExe -Leaf)" | Set-Content -Encoding ascii $hashFile

Write-Host ''
Write-Host 'SETUP R5c7 COMPLETATO'
Write-Host "Installer: $setupExe"
Write-Host "SHA-256: $hash"
Write-Host 'Il Setup installa sempre il Core; il runtime AI resta un componente opzionale e riutilizza runtime esterni validi quando possibile.'
