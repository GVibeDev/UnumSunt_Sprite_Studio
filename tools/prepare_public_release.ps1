param(
    [switch]$SkipBuild,
    [switch]$SkipTests,
    [switch]$AllowDirtySource
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
$Version = 'R5c7'
$PublicDir = Join-Path $Root "release\public\$Version"

function Write-Section([string]$Text) {
    Write-Host ''
    Write-Host "=== $Text ==="
}

function Require-File([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label non trovato: $Path"
    }
}

Write-Section 'Unum Sunt Sprite Studio R5c7 - Public Release Preparation'

$requiredSource = @(
    'LICENSE', 'THIRD_PARTY_NOTICES.txt', 'KREA_SAFETY_AND_USE.txt',
    'GPL_DISTRIBUTION_CHECKLIST.txt', 'RELEASE_NOTES_R5c7.md',
    'SECURITY.md', 'SOURCE_MANIFEST.json'
)
foreach ($rel in $requiredSource) { Require-File (Join-Path $Root $rel) $rel }

if (-not $SkipTests) {
    Write-Section 'Source regression'
    $buildPython = Join-Path $Root '.build-venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $buildPython) {
        & $buildPython -m unittest discover -s tests -p 'test_*.py'
        if ($LASTEXITCODE -ne 0) { throw 'Regression suite fallita.' }
        & $buildPython -m compileall app main.py
        if ($LASTEXITCODE -ne 0) { throw 'compileall fallito.' }
    }
    else {
        $py = Get-Command py.exe -ErrorAction SilentlyContinue
        if (-not $py) { throw '.build-venv assente e py.exe non disponibile.' }
        & $py.Source -3.13-64 -m unittest discover -s tests -p 'test_*.py'
        if ($LASTEXITCODE -ne 0) { throw 'Regression suite fallita.' }
        & $py.Source -3.13-64 -m compileall app main.py
        if ($LASTEXITCODE -ne 0) { throw 'compileall fallito.' }
    }
}

if (-not $SkipBuild) {
    Write-Section 'Canonical Windows Setup build'
    $args = @()
    if ($SkipTests) { $args += '-SkipTests' }
    & (Join-Path $Root 'build_setup_windows.ps1') @args
    if ($LASTEXITCODE -ne 0) { throw 'Build Setup R5c7 fallita.' }
}

$setup = Join-Path $Root 'release\installer\UnumSunt_Sprite_Studio_R5c7_Setup_x64.exe'
$setupSha = Join-Path $Root 'release\installer\UnumSunt_Sprite_Studio_R5c7_Setup_x64_SHA256.txt'
$standalone = Join-Path $Root 'release\UnumSunt_Sprite_Studio_R5c7_Windows_x64_Standalone.zip'
$standaloneSha = Join-Path $Root 'release\UnumSunt_Sprite_Studio_R5c7_Windows_x64_Standalone_SHA256.txt'
Require-File $setup 'Setup R5c7'
Require-File $setupSha 'Setup SHA-256'
Require-File $standalone 'Standalone ZIP'
Require-File $standaloneSha 'Standalone SHA-256'

Write-Section 'Git source identity'
$git = Get-Command git.exe -ErrorAction SilentlyContinue
$gitCommit = $null
$sourceZip = Join-Path $PublicDir 'UnumSunt_Sprite_Studio_R5c7_Source.zip'
New-Item -ItemType Directory -Force $PublicDir | Out-Null
Remove-Item -Force $sourceZip -ErrorAction SilentlyContinue

if ($git -and (Test-Path -LiteralPath (Join-Path $Root '.git'))) {
    $dirty = @(& $git.Source status --porcelain)
    if ($dirty.Count -gt 0 -and -not $AllowDirtySource) {
        Write-Host 'Working tree non pulito:' -ForegroundColor Yellow
        $dirty | ForEach-Object { Write-Host "  $_" }
        throw 'Committare la finalizzazione R5c7 prima di creare il Corresponding Source, oppure usare -AllowDirtySource solo per una prova locale.'
    }
    $gitCommit = (& $git.Source rev-parse HEAD).Trim()
    if (-not $AllowDirtySource) {
        & $git.Source archive --format=zip --prefix='UnumSunt_Sprite_Studio_R5c7/' -o $sourceZip HEAD
        if ($LASTEXITCODE -ne 0) { throw 'git archive fallito.' }
    }
}

if (-not (Test-Path -LiteralPath $sourceZip)) {
    # Fallback for a source tree that is not a Git checkout, or a deliberate dirty-tree test.
    $stageRoot = Join-Path $env:TEMP ("UnumSunt_R5c7_Source_" + [guid]::NewGuid().ToString('N'))
    $stage = Join-Path $stageRoot 'UnumSunt_Sprite_Studio_R5c7'
    New-Item -ItemType Directory -Force $stage | Out-Null
    $excludeDirs = @('.git','.venv','.build-venv','dist','build','release','__pycache__','.pytest_cache','ai_runtime','models','ckpts','WanGP','generation_jobs','logs')
    $excludeExt = @('.exe','.msi','.apk','.aab','.safetensors','.gguf','.ckpt','.pt','.pth','.onnx','.pyc')
    Get-ChildItem -LiteralPath $Root -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($Root.Length).TrimStart('\')
        $parts = $rel -split '[\\/]'
        if ($parts | Where-Object { $excludeDirs -contains $_ }) { return }
        if ($excludeExt -contains $_.Extension.ToLowerInvariant()) { return }
        if ($_.Name -like '.env*' -or $_.Extension -in @('.key','.pem')) { return }
        $dest = Join-Path $stage $rel
        New-Item -ItemType Directory -Force (Split-Path -Parent $dest) | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $dest
    }
    Compress-Archive -Path $stage -DestinationPath $sourceZip -CompressionLevel Optimal
    Remove-Item -Recurse -Force $stageRoot
}

Write-Section 'Assembling public artifact folder'
$copyFiles = @(
    $setup, $setupSha, $standalone, $standaloneSha,
    (Join-Path $Root 'RELEASE_NOTES_R5c7.md'),
    (Join-Path $Root 'LICENSE'),
    (Join-Path $Root 'THIRD_PARTY_NOTICES.txt'),
    (Join-Path $Root 'KREA_SAFETY_AND_USE.txt')
)
foreach ($src in $copyFiles) { Copy-Item -Force -LiteralPath $src -Destination $PublicDir }

$sourceHash = (Get-FileHash -Algorithm SHA256 $sourceZip).Hash.ToLowerInvariant()
$sourceSha = Join-Path $PublicDir 'UnumSunt_Sprite_Studio_R5c7_Source_SHA256.txt'
"$sourceHash  UnumSunt_Sprite_Studio_R5c7_Source.zip" | Set-Content -Encoding ascii $sourceSha

# Verify source archive contains the GPL payload.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($sourceZip)
try {
    $entries = @($zip.Entries | ForEach-Object { $_.FullName })
    foreach ($required in @('LICENSE','THIRD_PARTY_NOTICES.txt','RELEASE_NOTES_R5c7.md')) {
        if (-not ($entries -contains "UnumSunt_Sprite_Studio_R5c7/$required")) {
            throw "Corresponding Source incompleto: manca $required"
        }
    }
}
finally { $zip.Dispose() }

$setupHash = (Get-FileHash -Algorithm SHA256 $setup).Hash.ToLowerInvariant()
$standaloneHash = (Get-FileHash -Algorithm SHA256 $standalone).Hash.ToLowerInvariant()
$manifest = [ordered]@{
    schema = 'unum-sunt-public-release-v1'
    generated_at = (Get-Date).ToString('o')
    project = 'Unum Sunt Sprite Studio'
    version = $Version
    tag = $Version
    platform = 'Windows x64'
    core_license = 'GPL-3.0-or-later'
    git_commit = $gitCommit
    artifacts = @(
        [ordered]@{ file = (Split-Path $setup -Leaf); sha256 = $setupHash; role = 'Windows Setup' },
        [ordered]@{ file = (Split-Path $standalone -Leaf); sha256 = $standaloneHash; role = 'Standalone Core' },
        [ordered]@{ file = (Split-Path $sourceZip -Leaf); sha256 = $sourceHash; role = 'GPL Corresponding Source' }
    )
}
$manifestPath = Join-Path $PublicDir 'RELEASE_MANIFEST_R5c7.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 $manifestPath

Write-Host ''
Write-Host 'PUBLIC RELEASE PACKAGE READY' -ForegroundColor Green
Write-Host "Folder: $PublicDir"
Write-Host "Setup SHA-256:      $setupHash"
Write-Host "Standalone SHA-256: $standaloneHash"
Write-Host "Source SHA-256:     $sourceHash"
if ($gitCommit) { Write-Host "Git commit:          $gitCommit" }
Write-Host ''
Write-Host 'Nessun upload e nessun tag Git sono stati eseguiti automaticamente.'
