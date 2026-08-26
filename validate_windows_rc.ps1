param(
    [switch]$BuildSetup,
    [switch]$SkipBuild,
    [switch]$InstallInnoSetup
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$ExpectedVersion = 'R5c8'
$ExpectedProductVersion = '5.8.0.0'
$ExpectedExeName = 'UnumSuntSpriteStudio.exe'
$ExpectedSetupName = 'UnumSunt_Sprite_Studio_R5c8_Setup_x64.exe'
$AuditDir = Join-Path $PSScriptRoot 'release\audit'
New-Item -ItemType Directory -Force $AuditDir | Out-Null

$results = New-Object System.Collections.Generic.List[object]

function Add-Result([string]$Area, [string]$Status, [string]$Detail) {
    $entry = [pscustomobject]@{
        area = $Area
        status = $Status
        detail = $Detail
    }
    $script:results.Add($entry)
    $prefix = switch ($Status) {
        'PASS' { '[PASS]' }
        'WARN' { '[WARN]' }
        default { '[FAIL]' }
    }
    $color = switch ($Status) {
        'PASS' { 'Green' }
        'WARN' { 'Yellow' }
        default { 'Red' }
    }
    Write-Host "$prefix $Area - $Detail" -ForegroundColor $color
}

function Check-File([string]$Area, [string]$Path) {
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        Add-Result $Area 'PASS' $Path
        return $true
    }
    Add-Result $Area 'FAIL' "Missing file: $Path"
    return $false
}

function Run-PipCheck([string]$Area, [string]$PythonPath, [bool]$Required) {
    if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        Add-Result $Area ($(if ($Required) {'FAIL'} else {'WARN'})) "Python unavailable: $PythonPath"
        return
    }
    $output = & $PythonPath -m pip check 2>&1
    $exit = $LASTEXITCODE
    if ($exit -eq 0) {
        Add-Result $Area 'PASS' (($output | Out-String).Trim())
    }
    else {
        Add-Result $Area 'FAIL' (($output | Out-String).Trim())
    }
}

Write-Host ''
Write-Host '=== Unum Sunt Sprite Studio R5c8 - Windows RC Validation ===' -ForegroundColor Cyan
Write-Host "Repository: $PSScriptRoot"
Write-Host ''

# Repository / branding gate
Check-File 'Branding PNG' (Join-Path $PSScriptRoot 'assets\branding\app_icon.png') | Out-Null
Check-File 'Branding ICO' (Join-Path $PSScriptRoot 'assets\branding\app_icon.ico') | Out-Null
Check-File 'Splash' (Join-Path $PSScriptRoot 'assets\branding\splash_screen.png') | Out-Null
Check-File 'Installer wizard image' (Join-Path $PSScriptRoot 'assets\branding\installer_wizard.bmp') | Out-Null
Check-File 'Installer wizard small image' (Join-Path $PSScriptRoot 'assets\branding\installer_wizard_small.bmp') | Out-Null

$specPath = Join-Path $PSScriptRoot 'UnumSuntSpriteStudio.spec'
if (Check-File 'PyInstaller spec' $specPath) {
    $spec = Get-Content -LiteralPath $specPath -Raw
    if ($spec -match "icon='assets/branding/app_icon\.ico'") {
        Add-Result 'EXE icon contract' 'PASS' 'PyInstaller uses assets/branding/app_icon.ico'
    }
    else {
        Add-Result 'EXE icon contract' 'FAIL' 'EXE icon is not declared in the .spec file'
    }
}

$issPath = Join-Path $PSScriptRoot 'installer\UnumSuntSpriteStudio_R5c8.iss'
if (Check-File 'Inno Setup source' $issPath) {
    $iss = Get-Content -LiteralPath $issPath -Raw
    foreach ($needle in @('SetupIconFile=..\assets\branding\app_icon.ico', 'WizardImageFile=..\assets\branding\installer_wizard.bmp', 'WizardSmallImageFile=..\assets\branding\installer_wizard_small.bmp')) {
        if ($iss.Contains($needle)) {
            Add-Result 'Installer branding contract' 'PASS' $needle
        }
        else {
            Add-Result 'Installer branding contract' 'FAIL' "Missing: $needle"
        }
    }
}

# Build gate
if (-not $SkipBuild -and $BuildSetup) {
    try {
        Write-Host ''
        Write-Host 'Starting R5c8 Setup build...' -ForegroundColor Cyan
        $args = @()
        if ($InstallInnoSetup) { $args += '-InstallInnoSetup' }
        & (Join-Path $PSScriptRoot 'build_setup_windows.ps1') @args
        if ($LASTEXITCODE -ne 0) { throw "build_setup_windows.ps1 exit code $LASTEXITCODE" }
        Add-Result 'Windows build' 'PASS' 'Standalone + Setup completed'
    }
    catch {
        Add-Result 'Windows build' 'FAIL' $_.Exception.Message
    }
}
elseif ($SkipBuild) {
    Add-Result 'Windows build' 'WARN' 'Build skipped by request; existing artifacts will be validated.'
}
else {
    Add-Result 'Windows build' 'WARN' 'Build not requested. Run again with -BuildSetup for the complete gate.'
}

# Core dependency gate
$buildPython = Join-Path $PSScriptRoot '.build-venv\Scripts\python.exe'
Run-PipCheck 'Core pip check' $buildPython $true

# Standalone gate
$distDir = Join-Path $PSScriptRoot 'dist\UnumSuntSpriteStudio'
$exePath = Join-Path $distDir $ExpectedExeName
if (Check-File 'Standalone EXE' $exePath) {
    try {
        $versionOut = & $exePath --version 2>&1 | Out-String
        if ($versionOut -match [regex]::Escape($ExpectedVersion)) {
            Add-Result 'Frozen version' 'PASS' $versionOut.Trim()
        }
        else {
            Add-Result 'Frozen version' 'FAIL' "Expected $ExpectedVersion; got: $($versionOut.Trim())"
        }
    }
    catch {
        Add-Result 'Frozen version' 'FAIL' $_.Exception.Message
    }

    try {
        $vi = (Get-Item -LiteralPath $exePath).VersionInfo
        $numeric = [string]$vi.FileVersionRaw
        $detail = "FileVersion=$($vi.FileVersion); ProductVersion=$($vi.ProductVersion); Raw=$numeric"
        if ($detail -match [regex]::Escape($ExpectedVersion) -or $detail -match [regex]::Escape($ExpectedProductVersion)) {
            Add-Result 'Windows version resource' 'PASS' $detail
        }
        else {
            Add-Result 'Windows version resource' 'WARN' $detail
        }
    }
    catch {
        Add-Result 'Windows version resource' 'WARN' $_.Exception.Message
    }

    try {
        Add-Type -AssemblyName System.Drawing
        $icon = [System.Drawing.Icon]::ExtractAssociatedIcon($exePath)
        if ($null -eq $icon) {
            Add-Result 'EXE embedded icon' 'FAIL' 'Windows did not extract an associated icon.'
        }
        else {
            $preview = Join-Path $AuditDir 'exe_icon_preview.png'
            $bitmap = $icon.ToBitmap()
            $bitmap.Save($preview, [System.Drawing.Imaging.ImageFormat]::Png)
            $bitmap.Dispose()
            $icon.Dispose()
            Add-Result 'EXE embedded icon' 'PASS' "Extracted icon: $preview"
        }
    }
    catch {
        Add-Result 'EXE embedded icon' 'WARN' "Automated verification unavailable: $($_.Exception.Message)"
    }

    $selfCheckPath = Join-Path $AuditDir 'standalone_selfcheck_R5c8.json'
    try {
        Remove-Item -Force $selfCheckPath -ErrorAction SilentlyContinue
        $process = Start-Process -FilePath $exePath -ArgumentList @('--self-check', ('"{0}"' -f $selfCheckPath)) -Wait -PassThru
        if ($process.ExitCode -eq 0 -and (Test-Path -LiteralPath $selfCheckPath)) {
            $self = Get-Content -LiteralPath $selfCheckPath -Raw | ConvertFrom-Json
            if ($self.status -eq 'passed' -and $self.frozen) {
                Add-Result 'Frozen self-check' 'PASS' 'status=passed; frozen=true'
            }
            else {
                Add-Result 'Frozen self-check' 'FAIL' "status=$($self.status); frozen=$($self.frozen)"
            }
        }
        else {
            Add-Result 'Frozen self-check' 'FAIL' "Exit code $($process.ExitCode)"
        }
    }
    catch {
        Add-Result 'Frozen self-check' 'FAIL' $_.Exception.Message
    }
}

# Setup + checksum gate
$installerDir = Join-Path $PSScriptRoot 'release\installer'
$setupPath = Join-Path $installerDir $ExpectedSetupName
$setupHashPath = Join-Path $installerDir 'UnumSunt_Sprite_Studio_R5c8_Setup_x64_SHA256.txt'
if (Check-File 'Setup EXE' $setupPath) {
    if (Check-File 'Setup SHA256' $setupHashPath) {
        try {
            $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $setupPath).Hash.ToLowerInvariant()
            $expectedHash = ((Get-Content -LiteralPath $setupHashPath -Raw).Trim().Split()[0]).ToLowerInvariant()
            if ($actualHash -eq $expectedHash) {
                Add-Result 'Setup checksum' 'PASS' $actualHash
            }
            else {
                Add-Result 'Setup checksum' 'FAIL' "Expected $expectedHash; got $actualHash"
            }
        }
        catch {
            Add-Result 'Setup checksum' 'FAIL' $_.Exception.Message
        }
    }
}

# Runtime pip check from the user's real Sprite Studio configuration.
$configRoot = Join-Path $env:LOCALAPPDATA 'UnumSuntSpriteStudio'
$runtimePythons = New-Object System.Collections.Generic.HashSet[string]
foreach ($name in @('local_wangp.json', 'local_wangp_image.json')) {
    $path = Join-Path $configRoot $name
    if (-not (Test-Path -LiteralPath $path)) { continue }
    try {
        $cfg = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        if ($cfg.python_executable) { [void]$runtimePythons.Add([string]$cfg.python_executable) }
    }
    catch {
        Add-Result "Runtime config $name" 'WARN' $_.Exception.Message
    }
}
if ($runtimePythons.Count -eq 0) {
    Add-Result 'WanGP pip check' 'WARN' 'No configured WanGP Python was found in LOCALAPPDATA.'
}
else {
    $index = 1
    foreach ($runtimePython in $runtimePythons) {
        Run-PipCheck "WanGP pip check #$index" $runtimePython $false
        $index++
    }
}

# Manual Windows gates cannot be truthfully automated from the repository.
foreach ($gate in @(
    'Clean installation and launch',
    'Start Menu / Desktop / taskbar icon',
    'Real Krea Image Gen',
    'Real Wan Animate',
    'Krea -> reference -> Animate -> Video -> Sprite',
    'Upgrade from a previous version',
    'Repair the same R5c8 installation',
    'Conservative uninstall + reinstall',
    'Full uninstall on a disposable installation'
)) {
    Add-Result "Manual gate: $gate" 'WARN' 'Must be verified manually on the real Windows PC.'
}

$pass = @($results | Where-Object status -eq 'PASS').Count
$warn = @($results | Where-Object status -eq 'WARN').Count
$fail = @($results | Where-Object status -eq 'FAIL').Count
$overall = if ($fail -gt 0) { 'FAIL' } elseif ($warn -gt 0) { 'PASS_WITH_MANUAL_GATES' } else { 'PASS' }

$report = [pscustomobject]@{
    schema = 'unum-sunt-r5c8-windows-rc-validation-v1'
    generated_at = (Get-Date).ToString('o')
    expected_version = $ExpectedVersion
    overall = $overall
    counts = [pscustomobject]@{ pass = $pass; warning = $warn; fail = $fail }
    results = $results
}

$jsonPath = Join-Path $AuditDir 'R5c8_WINDOWS_RC_VALIDATION.json'
$textPath = Join-Path $AuditDir 'R5c8_WINDOWS_RC_VALIDATION.txt'
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
@(
    "Unum Sunt Sprite Studio R5c8 - Windows RC Validation",
    "Overall: $overall",
    "PASS=$pass WARN=$warn FAIL=$fail",
    '',
    ($results | ForEach-Object { "[$($_.status)] $($_.area) - $($_.detail)" })
) | Set-Content -LiteralPath $textPath -Encoding UTF8

Write-Host ''
Write-Host "REPORT: $jsonPath" -ForegroundColor Cyan
Write-Host "SUMMARY: $textPath" -ForegroundColor Cyan
Write-Host "OVERALL: $overall (PASS=$pass WARN=$warn FAIL=$fail)" -ForegroundColor $(if ($fail -gt 0) {'Red'} elseif ($warn -gt 0) {'Yellow'} else {'Green'})

if ($fail -gt 0) { exit 2 }
exit 0
