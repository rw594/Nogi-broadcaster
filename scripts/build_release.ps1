param(
  [string]$BackendPath = "",
  [string]$NpcapInstaller = "",
  [string]$ReleaseName = "",
  [string]$ReleaseConfigPath = "",
  [string]$LocalConfigPath = "",
  [string]$ReadmePath = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
$rootFull = [System.IO.Path]::GetFullPath($root)
$iconPath = Join-Path $root "assets\icon\buffwatcher.ico"
$productName = ([string][char]0x6D1B + [string][char]0x5947 + [string][char]0x64AD + [string][char]0x62A5 + [string][char]0x5C0F + [string][char]0x52A9 + [string][char]0x624B)
$runtimeDirName = ([string][char]0x7A0B + [string][char]0x5E8F + [string][char]0x6587 + [string][char]0x4EF6)

if ([string]::IsNullOrWhiteSpace($ReleaseName)) {
  $ReleaseName = ($productName + "-test")
} elseif ($ReleaseName.StartsWith($productName, [System.StringComparison]::Ordinal)) {
  $ReleaseName = $ReleaseName.Trim()
} elseif ($ReleaseName.EndsWith("test", [System.StringComparison]::OrdinalIgnoreCase) -and ($ReleaseName -notmatch '^[Vv]\d')) {
  $ReleaseName = ($productName + "-test")
} elseif (-not $ReleaseName.StartsWith($productName, [System.StringComparison]::Ordinal)) {
  $ReleaseName = ($productName + " " + $ReleaseName.Trim())
}

$versionMatch = [regex]::Match($ReleaseName, '(?:^|\s)(V\d+(?:\.\d+)+(?:[A-Za-z])?)(?:\s|$)', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
$versionLabel = ""
if ($versionMatch.Success) {
  $versionLabel = $versionMatch.Groups[1].Value
  if ($versionLabel.StartsWith("v", [System.StringComparison]::Ordinal)) {
    $versionLabel = "V" + $versionLabel.Substring(1)
  }
}
$displayName = $productName
if ($versionLabel) {
  $displayName = ($productName + " " + $versionLabel)
}
$entryFileName = ($productName + ".exe")
$versionCode = 0
if ($versionLabel) {
  $parsedVersion = [regex]::Match($versionLabel, '^[Vv](?<major>\d+)\.(?<minor>\d+)(?:\.(?<patch>\d+))?(?<suffix>[A-Za-z])?$')
  if ($parsedVersion.Success) {
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
    $versionCode = ($major * 10000) + ($minor * 100) + $patch
  }
}
$updateMetadataUrl = "https://github.com/rw594/Nogi-broadcaster/releases/latest/download/latest.json"

function Assert-UnderRoot([string]$PathToCheck) {
  $full = [System.IO.Path]::GetFullPath($PathToCheck)
  $prefix = $rootFull.TrimEnd('\') + '\'
  if (-not $full.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to modify outside workspace: $full"
  }
}

function Assert-UnderDirectory([string]$PathToCheck, [string]$BaseDirectory) {
  $full = [System.IO.Path]::GetFullPath($PathToCheck)
  $base = [System.IO.Path]::GetFullPath($BaseDirectory).TrimEnd('\') + '\'
  if (-not $full.StartsWith($base, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to modify outside target directory: $full"
  }
}

function Find-LatestDesktopConfig([string]$DesktopDrop) {
  if (-not (Test-Path -LiteralPath $DesktopDrop)) {
    return $null
  }
  $candidates = Get-ChildItem -LiteralPath $DesktopDrop -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '(?:^|\s)V(?<major>\d+)\.(?<minor>\d+)' } |
    ForEach-Object {
      $match = [regex]::Match($_.Name, '(?:^|\s)V(?<major>\d+)\.(?<minor>\d+)')
      $configCandidates = @(
        (Join-Path (Join-Path (Join-Path $_.FullName $runtimeDirName) "BuffWatcher") "buffwatcher.config.local.json"),
        (Join-Path $_.FullName "BuffWatcher\buffwatcher.config.local.json")
      )
      $config = $configCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
      if ($config -and (Test-Path -LiteralPath $config)) {
        [PSCustomObject]@{
          Path = $config
          Major = [int]$match.Groups["major"].Value
          Minor = [int]$match.Groups["minor"].Value
          LastWriteTime = $_.LastWriteTime
        }
      }
    } |
    Sort-Object -Property Major, Minor, LastWriteTime -Descending |
    Select-Object -First 1
  if ($candidates) {
    return $candidates.Path
  }
  return $null
}

if (-not $BackendPath) {
  $candidates = @(
    ".\vendor\mabicat.exe",
    "$env:TEMP\3Cx0LYeZkIYbB63mHmwf2lv5SME\resources\mabicat.exe"
  )
  $BackendPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

if (-not $BackendPath -or -not (Test-Path -LiteralPath $BackendPath)) {
  throw "mabicat.exe not found. Pass -BackendPath C:\path\to\mabicat.exe"
}

if (-not $NpcapInstaller) {
  $NpcapInstaller = Get-ChildItem -Path "C:\Users\rw594\Desktop\MicoPunch" -Recurse -Filter "npcap-1.87.exe" -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty FullName -First 1
}

$desktopDrop = Join-Path $env:USERPROFILE ("Desktop\BUFF" + [char]0x8FFD + [char]0x8E2A + [char]0x5668)

if (-not $ReleaseConfigPath) {
  $ReleaseConfigPath = Join-Path $root "buffwatcher.config.defaults.json"
}
if (-not (Test-Path -LiteralPath $ReleaseConfigPath)) {
  $ReleaseConfigPath = Join-Path $root "buffwatcher.config.local.json"
}
if (-not (Test-Path -LiteralPath $ReleaseConfigPath)) {
  throw "Release config not found: $ReleaseConfigPath"
}

if (-not $LocalConfigPath) {
  $LocalConfigPath = Find-LatestDesktopConfig $desktopDrop
}
if (-not $LocalConfigPath) {
  $LocalConfigPath = Join-Path $root "buffwatcher.config.local.json"
}

if (-not $ReadmePath) {
  $ReadmePath = Join-Path $env:USERPROFILE ("Desktop\" + [char]0x4F7F + [char]0x7528 + [char]0x8BF4 + [char]0x660E + ".txt")
}
if (-not (Test-Path -LiteralPath $ReadmePath)) {
  $ReadmePath = Join-Path $root "docs\release-readme-zh.txt"
}
if (-not (Test-Path -LiteralPath $ReadmePath)) {
  throw "README source not found: $ReadmePath"
}

$vendorDir = Join-Path $root "vendor"
New-Item -ItemType Directory -Force -Path $vendorDir | Out-Null
$vendorBackend = Join-Path $vendorDir "mabicat.exe"
if ([System.IO.Path]::GetFullPath($BackendPath) -ne [System.IO.Path]::GetFullPath($vendorBackend)) {
  Copy-Item -LiteralPath $BackendPath -Destination $vendorBackend -Force
}

$watcherArgs = @(
  "--noconfirm",
  "--clean",
  "--onedir",
  "--console",
  "--name", "BuffWatcher",
  "--paths", $root
)
if (Test-Path -LiteralPath $iconPath) {
  $watcherArgs += @("--icon", $iconPath)
}
$watcherArgs += "run_standalone.py"
python -m PyInstaller @watcherArgs

$consoleArgs = @(
  "--noconfirm",
  "--clean",
  "--onedir",
  "--console",
  "--name", "BuffWatcherConsole",
  "--paths", $root
)
if (Test-Path -LiteralPath $iconPath) {
  $consoleArgs += @("--icon", $iconPath)
}
$consoleArgs += "run_console.py"
python -m PyInstaller @consoleArgs

$launcherArgs = @(
  "--noconfirm",
  "--clean",
  "--onedir",
  "--windowed",
  "--name", "BuffWatcherLauncher",
  "--paths", $root
)
if (Test-Path -LiteralPath $iconPath) {
  $launcherArgs += @("--icon", $iconPath)
}
$launcherArgs += "run_launcher.py"
python -m PyInstaller @launcherArgs

$settingsArgs = @(
  "--noconfirm",
  "--clean",
  "--onedir",
  "--windowed",
  "--name", "BuffWatcherSettings",
  "--paths", $root
)
if (Test-Path -LiteralPath $iconPath) {
  $settingsArgs += @("--icon", $iconPath)
}
$settingsArgs += "run_settings.py"
python -m PyInstaller @settingsArgs

$entryArgs = @(
  "--noconfirm",
  "--clean",
  "--onefile",
  "--windowed",
  "--name", "BuffWatcherStart",
  "--paths", $root
)
if (Test-Path -LiteralPath $iconPath) {
  $entryArgs += @("--icon", $iconPath)
}
$entryArgs += "run_entry.py"
python -m PyInstaller @entryArgs

$releaseRoot = Join-Path $root "release"
$packageRoot = Join-Path $releaseRoot $ReleaseName
$runtimeRoot = Join-Path $packageRoot $runtimeDirName
$appRoot = Join-Path $runtimeRoot "BuffWatcher"
$consoleRoot = Join-Path $runtimeRoot "BuffWatcherConsole"
$launcherRoot = Join-Path $runtimeRoot "BuffWatcherLauncher"
$settingsRoot = Join-Path $runtimeRoot "BuffWatcherSettings"

if (Test-Path -LiteralPath $packageRoot) {
  Assert-UnderRoot $packageRoot
  Remove-Item -LiteralPath $packageRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null

$packageInfo = [ordered]@{
  product_name = $productName
  version_label = $versionLabel
  version_code = $versionCode
  display_name = $displayName
  release_name = $ReleaseName
  update_url = $updateMetadataUrl
}
$packageInfoJson = $packageInfo | ConvertTo-Json -Depth 3
[System.IO.File]::WriteAllText((Join-Path $runtimeRoot "package-info.json"), $packageInfoJson, [System.Text.UTF8Encoding]::new($false))

Copy-Item -Path ".\dist\BuffWatcher" -Destination $runtimeRoot -Recurse -Force
Copy-Item -Path ".\dist\BuffWatcherConsole" -Destination $runtimeRoot -Recurse -Force
Copy-Item -Path ".\dist\BuffWatcherLauncher" -Destination $runtimeRoot -Recurse -Force
Copy-Item -Path ".\dist\BuffWatcherSettings" -Destination $runtimeRoot -Recurse -Force
Copy-Item -LiteralPath ".\dist\BuffWatcherStart.exe" -Destination (Join-Path $packageRoot $entryFileName) -Force
Copy-Item -LiteralPath $ReleaseConfigPath -Destination (Join-Path $appRoot "buffwatcher.config.local.json") -Force
$defaultConfigDir = Join-Path $appRoot "config"
New-Item -ItemType Directory -Force -Path $defaultConfigDir | Out-Null
Copy-Item -LiteralPath (Join-Path $root "buffwatcher.config.defaults.json") -Destination (Join-Path $defaultConfigDir "buffwatcher.config.defaults.json") -Force
Copy-Item -Path ".\assets" -Destination $appRoot -Recurse -Force
Copy-Item -Path ".\vendor" -Destination $appRoot -Recurse -Force

$readmeFileName = ([string][char]0x4F7F + [string][char]0x7528 + [string][char]0x65B9 + [string][char]0x6CD5 + "README.txt")
Copy-Item -LiteralPath $ReadmePath -Destination (Join-Path $packageRoot $readmeFileName) -Force

if (Test-Path -LiteralPath $NpcapInstaller) {
  $npcapDir = Join-Path $packageRoot "Npcap"
  New-Item -ItemType Directory -Force -Path $npcapDir | Out-Null
  Copy-Item -LiteralPath $NpcapInstaller -Destination $npcapDir -Force
}

$zipPath = Join-Path $releaseRoot "$ReleaseName.zip"
if (Test-Path -LiteralPath $zipPath) {
  Assert-UnderRoot $zipPath
  Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force

if ($LocalConfigPath -and (Test-Path -LiteralPath $LocalConfigPath)) {
  Copy-Item -LiteralPath $LocalConfigPath -Destination (Join-Path $appRoot "buffwatcher.config.local.json") -Force
  Write-Host ("local folder config: " + $LocalConfigPath)
}

if (Test-Path -LiteralPath (Split-Path -Parent $desktopDrop)) {
  New-Item -ItemType Directory -Force -Path $desktopDrop | Out-Null
  $desktopZip = Join-Path $desktopDrop (Split-Path -Leaf $zipPath)
  Copy-Item -LiteralPath $zipPath -Destination $desktopZip -Force
  $desktopPackage = Join-Path $desktopDrop $ReleaseName
  if (Test-Path -LiteralPath $desktopPackage) {
    Assert-UnderDirectory $desktopPackage $desktopDrop
    Remove-Item -LiteralPath $desktopPackage -Recurse -Force
  }
  Copy-Item -LiteralPath $packageRoot -Destination $desktopDrop -Recurse -Force
  Write-Host ("desktop zip: " + $desktopZip)
  Write-Host ("desktop folder: " + $desktopPackage)
}

Write-Host ("release config for zip: " + $ReleaseConfigPath)
Write-Host ("README source: " + $ReadmePath)
Write-Host "release: $packageRoot"
Write-Host "zip: $zipPath"
