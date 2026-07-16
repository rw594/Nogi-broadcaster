param(
  [string]$BackendPath = "",
  [string]$NpcapInstaller = "",
  [string]$ReleaseName = "",
  [string]$ReleaseConfigPath = "",
  [string]$LocalConfigPath = "",
  [string]$ReadmePath = "",
  [string[]]$UpdateMetadataUrls = @(),
  [string]$UpdateChannelId = "nogi-v13-public",
  [bool]$StrictUpdateChannel = $true,
  [int]$VersionCodeOverride = 0,
  [switch]$IncludeVisualOverlay,
  [switch]$PrivateBuild,
  [switch]$SkipProjectFolderCopy
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
$rootFull = [System.IO.Path]::GetFullPath($root)
$iconPath = Join-Path $root "assets\icon\buffwatcher.ico"
$productName = ([string][char]0x6D1B + [string][char]0x5947 + [string][char]0x64AD + [string][char]0x62A5 + [string][char]0x5C0F + [string][char]0x52A9 + [string][char]0x624B)
$runtimeDirName = ([string][char]0x7A0B + [string][char]0x5E8F + [string][char]0x6587 + [string][char]0x4EF6)
$publicLocalFolderName = ([string][char]0x901A + [string][char]0x7528 + [string][char]0x7248)
$visualLocalFolderName = (
  [string][char]0x89C6 + [string][char]0x89C9 + "Overlay" +
  [string][char]0x5185 + [string][char]0x6D4B + [string][char]0x7248
)
$archiveFolderName = ([string][char]0x65E7 + [string][char]0x7248 + [string][char]0x7559 + [string][char]0x5B58)
$localFolderName = $publicLocalFolderName
if ($PrivateBuild -and $IncludeVisualOverlay) {
  $localFolderName = $visualLocalFolderName
}

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
if ($VersionCodeOverride -gt 0) {
  $versionCode = $VersionCodeOverride
}
# V1.3 starts a new, strictly isolated update generation.  All legacy and v2
# manifests remain disabled and must never be reused or redirected here.
$aliyunUpdateMetadataUrl = "https://nogi-broadcaster-updates.oss-cn-hangzhou.aliyuncs.com/channels/v13/public/latest.json"
$githubUpdateMetadataUrl = "https://raw.githubusercontent.com/rw594/Nogi-broadcaster/main/update-channels/v13/public/latest.json"
if (($UpdateMetadataUrls.Count -eq 0) -and $env:NOGI_UPDATE_METADATA_URLS) {
  $UpdateMetadataUrls = @(
    $env:NOGI_UPDATE_METADATA_URLS.Split(';') |
      ForEach-Object { $_.Trim() } |
      Where-Object { $_ }
  )
}
$normalizedUpdateMetadataUrls = @()
$metadataCandidates = @($UpdateMetadataUrls)
if (-not $PrivateBuild) {
  $metadataCandidates += @($aliyunUpdateMetadataUrl, $githubUpdateMetadataUrl)
}
if ((-not $PrivateBuild) -or ($metadataCandidates.Count -gt 0)) {
  foreach ($candidate in $metadataCandidates) {
    $value = [string]$candidate
    if ([string]::IsNullOrWhiteSpace($value)) {
      continue
    }
    $value = $value.Trim()
    if ($normalizedUpdateMetadataUrls -notcontains $value) {
      $normalizedUpdateMetadataUrls += $value
    }
  }
}
$updateMetadataUrl = ""
if ($normalizedUpdateMetadataUrls.Count -gt 0) {
  $updateMetadataUrl = $normalizedUpdateMetadataUrls[0]
}
if ($StrictUpdateChannel) {
  if ([string]::IsNullOrWhiteSpace($UpdateChannelId)) {
    throw "Strict update packages require a non-empty UpdateChannelId."
  }
  $allowedUrls = @()
  if ($UpdateChannelId -eq "nogi-v13-public") {
    $allowedUrls = @($aliyunUpdateMetadataUrl, $githubUpdateMetadataUrl)
  } elseif ($UpdateChannelId -eq "nogi-v13-visual") {
    $allowedUrls = @(
      "https://nogi-broadcaster-updates.oss-cn-hangzhou.aliyuncs.com/channels/v13/visual/latest.json"
    )
  } else {
    throw "Unknown strict update channel: $UpdateChannelId"
  }
  if ($normalizedUpdateMetadataUrls.Count -eq 0) {
    throw "Strict update packages require at least one metadata URL."
  }
  foreach ($metadataUrl in $normalizedUpdateMetadataUrls) {
    if ($allowedUrls -notcontains $metadataUrl) {
      throw "Strict update channel $UpdateChannelId refuses metadata URL: $metadataUrl"
    }
  }
}

function Assert-UnderRoot([string]$PathToCheck) {
  $full = [System.IO.Path]::GetFullPath($PathToCheck)
  $prefix = $rootFull.TrimEnd('\') + '\'
  if (-not $full.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to modify outside workspace: $full"
  }
}

function Get-RunningProcessesUnderDirectory([string]$Directory) {
  if (-not (Test-Path -LiteralPath $Directory)) {
    return @()
  }
  $directoryFull = [System.IO.Path]::GetFullPath($Directory).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
  ) + [System.IO.Path]::DirectorySeparatorChar
  $matches = @()
  foreach ($process in (Get-Process -ErrorAction SilentlyContinue)) {
    try {
      $processPath = $process.Path
    } catch {
      continue
    }
    if ([string]::IsNullOrWhiteSpace($processPath)) {
      continue
    }
    try {
      $processFull = [System.IO.Path]::GetFullPath($processPath)
    } catch {
      continue
    }
    if ($processFull.StartsWith($directoryFull, [System.StringComparison]::OrdinalIgnoreCase)) {
      $matches += $process
    }
  }
  return $matches
}

function Assert-UnderDirectory([string]$PathToCheck, [string]$BaseDirectory) {
  $full = [System.IO.Path]::GetFullPath($PathToCheck)
  $base = [System.IO.Path]::GetFullPath($BaseDirectory).TrimEnd('\') + '\'
  if (-not $full.StartsWith($base, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to modify outside target directory: $full"
  }
}

function Find-LatestPackageConfig([string]$PackageDrop) {
  if (-not (Test-Path -LiteralPath $PackageDrop)) {
    return $null
  }
  $candidates = Get-ChildItem -LiteralPath $PackageDrop -Directory -ErrorAction SilentlyContinue |
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

$documentsRoot = [Environment]::GetFolderPath([Environment+SpecialFolder]::MyDocuments)
$projectDrop = Join-Path (Join-Path $documentsRoot $productName) $productName

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
  $stableConfigCandidates = @(
    (Join-Path (Join-Path (Join-Path (Join-Path $projectDrop $localFolderName) $runtimeDirName) "BuffWatcher") "buffwatcher.config.local.json"),
    (Join-Path (Join-Path $projectDrop $localFolderName) "BuffWatcher\buffwatcher.config.local.json")
  )
  $LocalConfigPath = $stableConfigCandidates |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1
}
if (-not $LocalConfigPath) {
  $LocalConfigPath = Find-LatestPackageConfig $projectDrop
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

if ($IncludeVisualOverlay) {
  $overlayArgs = @(
    "--noconfirm",
    "--clean",
    "--onedir",
    "--windowed",
    "--name", "BuffWatcherOverlay",
    "--paths", $root
  )
  if (Test-Path -LiteralPath $iconPath) {
    $overlayArgs += @("--icon", $iconPath)
  }
  $overlayArgs += "run_overlay.py"
  python -m PyInstaller @overlayArgs
}

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
  update_urls = @($normalizedUpdateMetadataUrls)
  update_channel = $UpdateChannelId
  strict_update_channel = [bool]$StrictUpdateChannel
  private_build = [bool]$PrivateBuild
  visual_overlay = [bool]$IncludeVisualOverlay
}
$packageInfoJson = $packageInfo | ConvertTo-Json -Depth 3
[System.IO.File]::WriteAllText((Join-Path $runtimeRoot "package-info.json"), $packageInfoJson, [System.Text.UTF8Encoding]::new($false))

$installMarker = [ordered]@{
  product_name = $productName
  update_channel = $UpdateChannelId
  strict_update_channel = [bool]$StrictUpdateChannel
}
$installMarkerJson = $installMarker | ConvertTo-Json -Depth 2
[System.IO.File]::WriteAllText((Join-Path $packageRoot "nogi-install-root.json"), $installMarkerJson, [System.Text.UTF8Encoding]::new($false))

Copy-Item -Path ".\dist\BuffWatcher" -Destination $runtimeRoot -Recurse -Force
Copy-Item -Path ".\dist\BuffWatcherConsole" -Destination $runtimeRoot -Recurse -Force
Copy-Item -Path ".\dist\BuffWatcherLauncher" -Destination $runtimeRoot -Recurse -Force
Copy-Item -Path ".\dist\BuffWatcherSettings" -Destination $runtimeRoot -Recurse -Force
if ($IncludeVisualOverlay) {
  Copy-Item -Path ".\dist\BuffWatcherOverlay" -Destination $runtimeRoot -Recurse -Force
}
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

if (Test-Path -LiteralPath (Split-Path -Parent $projectDrop)) {
  New-Item -ItemType Directory -Force -Path $projectDrop | Out-Null
  $archiveRoot = Join-Path $projectDrop $archiveFolderName
  New-Item -ItemType Directory -Force -Path $archiveRoot | Out-Null
  $projectZip = Join-Path $archiveRoot (Split-Path -Leaf $zipPath)
  Copy-Item -LiteralPath $zipPath -Destination $projectZip -Force
  $projectPackage = Join-Path $projectDrop $localFolderName
  if ($SkipProjectFolderCopy) {
    Write-Host ("project folder copy skipped: " + $projectPackage)
  } else {
    $runningProjectProcesses = @(
      Get-RunningProcessesUnderDirectory $projectPackage
    )
    if ($runningProjectProcesses.Count -gt 0) {
      $runningSummary = (
        $runningProjectProcesses |
        ForEach-Object { $_.ProcessName + "(" + $_.Id + ")" }
      ) -join ", "
      Write-Warning (
        "Project folder is still running; local folder replacement was skipped " +
        "before any files were touched: " + $projectPackage + " :: " +
        $runningSummary
      )
      Write-Host ("project zip: " + $projectZip)
      Write-Host "release: $packageRoot"
      Write-Host "zip: $zipPath"
      return
    }
    $preserveRoot = Join-Path $releaseRoot ("local-preserve-" + $localFolderName)
    $preservedRelativePaths = @(
      (Join-Path $runtimeDirName "BuffWatcher\logs"),
      (Join-Path $runtimeDirName "BuffWatcher\assets\custom")
    )
    try {
      if (Test-Path -LiteralPath $preserveRoot) {
        Assert-UnderRoot $preserveRoot
        Remove-Item -LiteralPath $preserveRoot -Recurse -Force
      }
      if (Test-Path -LiteralPath $projectPackage) {
        Assert-UnderDirectory $projectPackage $projectDrop
        foreach ($relativePath in $preservedRelativePaths) {
          $sourcePath = Join-Path $projectPackage $relativePath
          if (-not (Test-Path -LiteralPath $sourcePath)) {
            continue
          }
          $preservePath = Join-Path $preserveRoot $relativePath
          New-Item -ItemType Directory -Force -Path (Split-Path -Parent $preservePath) | Out-Null
          Copy-Item -LiteralPath $sourcePath -Destination $preservePath -Recurse -Force
        }
        Remove-Item -LiteralPath $projectPackage -Recurse -Force
      }
      Copy-Item -LiteralPath $packageRoot -Destination $projectPackage -Recurse -Force
      foreach ($relativePath in $preservedRelativePaths) {
        $preservePath = Join-Path $preserveRoot $relativePath
        if (-not (Test-Path -LiteralPath $preservePath)) {
          continue
        }
        $restorePath = Join-Path $projectPackage $relativePath
        if (Test-Path -LiteralPath $restorePath) {
          Assert-UnderDirectory $restorePath $projectPackage
          Remove-Item -LiteralPath $restorePath -Recurse -Force
        }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $restorePath) | Out-Null
        Copy-Item -LiteralPath $preservePath -Destination $restorePath -Recurse -Force
      }
      Write-Host ("project folder: " + $projectPackage)
    } catch {
      if (-not $PrivateBuild) {
        throw
      }
      Write-Warning (
        "Private project folder was not replaced (likely still running). " +
        "The ZIP was updated successfully: " + $projectZip
      )
    } finally {
      if (Test-Path -LiteralPath $preserveRoot) {
        Assert-UnderRoot $preserveRoot
        Remove-Item -LiteralPath $preserveRoot -Recurse -Force
      }
    }
  }
  Write-Host ("project zip: " + $projectZip)
}

Write-Host ("release config for zip: " + $ReleaseConfigPath)
Write-Host ("README source: " + $ReadmePath)
Write-Host "release: $packageRoot"
Write-Host "zip: $zipPath"
