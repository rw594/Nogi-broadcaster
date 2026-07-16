param(
  [string]$Version = "",
  [string]$BackendPath = "",
  [string]$NpcapInstaller = "",
  [string]$ReadmePath = "",
  [int]$VisualRevision = 1,
  [string]$VisualUpdateMetadataUrl = "https://nogi-broadcaster-updates.oss-cn-hangzhou.aliyuncs.com/channels/v13/visual/latest.json",
  [string]$UpdateChannelId = "nogi-v13-visual",
  [switch]$SkipProjectFolderCopy
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

if ([string]::IsNullOrWhiteSpace($Version)) {
  $latestPath = Join-Path $root "latest.json"
  $latest = [System.IO.File]::ReadAllText($latestPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
  $Version = [string]$latest.version
}
$Version = $Version.Trim().TrimStart([char[]]@('v', 'V'))
if ([string]::IsNullOrWhiteSpace($Version)) {
  throw "Could not determine a version for the private visual build."
}
if ($VisualRevision -lt 1 -or $VisualRevision -gt 99) {
  throw "VisualRevision must be between 1 and 99."
}
$parsedVersion = [regex]::Match(
  $Version,
  '^(?<major>\d+)\.(?<minor>\d+)(?:\.(?<patch>\d+))?(?<suffix>[A-Za-z])?$'
)
if (-not $parsedVersion.Success) {
  throw "Could not calculate the visual update version code from: $Version"
}
$major = [int]$parsedVersion.Groups["major"].Value
$minor = [int]$parsedVersion.Groups["minor"].Value
$patch = 0
if ($parsedVersion.Groups["patch"].Success) {
  $patch = [int]$parsedVersion.Groups["patch"].Value
}
if ($parsedVersion.Groups["suffix"].Success) {
  $suffix = $parsedVersion.Groups["suffix"].Value.ToLowerInvariant()
  $patch += ([int][char]$suffix[0] - [int][char]'a') + 1
}
$baseVersionCode = ($major * 10000) + ($minor * 100) + $patch
$visualVersionCode = ($baseVersionCode * 100) + $VisualRevision

$productName = (
  [string][char]0x6D1B + [string][char]0x5947 + [string][char]0x64AD +
  [string][char]0x62A5 + [string][char]0x5C0F + [string][char]0x52A9 +
  [string][char]0x624B
)
$runtimeDirName = (
  [string][char]0x7A0B + [string][char]0x5E8F + [string][char]0x6587 +
  [string][char]0x4EF6
)
$visualLabel = (
  [string][char]0x89C6 + [string][char]0x89C9 + "Overlay" +
  [string][char]0x5185 + [string][char]0x6D4B + [string][char]0x7248
)
$documentsRoot = [Environment]::GetFolderPath([Environment+SpecialFolder]::MyDocuments)
$projectDrop = Join-Path (Join-Path $documentsRoot $productName) $productName

$scratch = Join-Path $root "scratch\visual-private"
New-Item -ItemType Directory -Force -Path $scratch | Out-Null
$releaseConfig = Join-Path $scratch "buffwatcher.visual-private.release.json"
$localConfig = Join-Path $scratch "buffwatcher.visual-private.local.json"

python scripts\make_visual_private_config.py `
  --base buffwatcher.config.defaults.json `
  --output $releaseConfig
if ($LASTEXITCODE -ne 0) {
  throw "Failed to generate the private release config."
}

$localBase = $null
if (Test-Path -LiteralPath $projectDrop) {
  $stableVisualConfig = Join-Path (
    Join-Path (Join-Path (Join-Path $projectDrop $visualLabel) $runtimeDirName) "BuffWatcher"
  ) "buffwatcher.config.local.json"
  if (Test-Path -LiteralPath $stableVisualConfig) {
    $localBase = $stableVisualConfig
  } else {
    $localBase = Get-ChildItem -LiteralPath $projectDrop -Directory -ErrorAction SilentlyContinue |
      Where-Object { $_.Name.EndsWith($visualLabel, [System.StringComparison]::Ordinal) } |
      Sort-Object LastWriteTime -Descending |
      ForEach-Object {
        Join-Path (Join-Path (Join-Path $_.FullName $runtimeDirName) "BuffWatcher") "buffwatcher.config.local.json"
      } |
      Where-Object { Test-Path -LiteralPath $_ } |
      Select-Object -First 1
  }
}
if (-not $localBase) {
  $localBase = Join-Path $root "buffwatcher.config.local.json"
}
if (-not (Test-Path -LiteralPath $localBase)) {
  $localBase = Join-Path $root "buffwatcher.config.defaults.json"
}
Write-Host ("visual local settings baseline: " + $localBase)
python scripts\make_visual_private_config.py `
  --base $localBase `
  --output $localConfig `
  --preserve-existing
if ($LASTEXITCODE -ne 0) {
  throw "Failed to generate the private local config."
}

$buildArguments = @{
  ReleaseName = ("V" + $Version + " " + $visualLabel)
  ReleaseConfigPath = $releaseConfig
  LocalConfigPath = $localConfig
  IncludeVisualOverlay = $true
  PrivateBuild = $true
  UpdateMetadataUrls = @($VisualUpdateMetadataUrl)
  UpdateChannelId = $UpdateChannelId
  StrictUpdateChannel = $true
  VersionCodeOverride = $visualVersionCode
  SkipProjectFolderCopy = $SkipProjectFolderCopy
}
if (-not [string]::IsNullOrWhiteSpace($BackendPath)) {
  $buildArguments.BackendPath = $BackendPath
}
if (-not [string]::IsNullOrWhiteSpace($NpcapInstaller)) {
  $buildArguments.NpcapInstaller = $NpcapInstaller
}
if (-not [string]::IsNullOrWhiteSpace($ReadmePath)) {
  $buildArguments.ReadmePath = $ReadmePath
}

& scripts\build_release.ps1 @buildArguments
Write-Host ("visual update revision: " + $VisualRevision)
Write-Host ("visual update version code: " + $visualVersionCode)
Write-Host ("visual update metadata: " + $VisualUpdateMetadataUrl)
