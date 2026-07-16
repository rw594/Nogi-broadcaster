param(
  [Parameter(Mandatory=$true)][string]$BucketUri,
  [Parameter(Mandatory=$true)][string]$PublicBaseUrl,
  [string]$ZipPath = "",
  [string]$ManifestPath = "",
  [string]$ManifestObject = "v2/latest.json",
  [string]$ChannelRoot = "",
  [string]$OssutilPath = "ossutil",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$ChannelRoot = $ChannelRoot.Trim().Trim('/')
$isV13Channel = $ChannelRoot -eq "channels/v13/public"
$updateDisableFlag = Join-Path $root "AUTO_UPDATE_DISABLED"
if ((Test-Path -LiteralPath $updateDisableFlag) -and -not $isV13Channel) {
  throw "Automatic update publishing is disabled by AUTO_UPDATE_DISABLED. Audit and fix the updater before removing the block."
}
if ($isV13Channel -and $ManifestObject.Trim().TrimStart('/') -ne "channels/v13/public/latest.json") {
  throw "The V1.3 public channel can only publish channels/v13/public/latest.json."
}

if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
  $ManifestPath = Join-Path $root "latest.json"
}
if (-not (Test-Path -LiteralPath $ManifestPath)) {
  throw "Update manifest not found: $ManifestPath"
}

$manifest = [System.IO.File]::ReadAllText(
  [System.IO.Path]::GetFullPath($ManifestPath),
  [System.Text.Encoding]::UTF8
) | ConvertFrom-Json
if ($isV13Channel -and ([string]$manifest.channel).Trim() -ne "nogi-v13-public") {
  throw "The V1.3 manifest must declare channel=nogi-v13-public."
}
$version = ([string]$manifest.version).Trim().TrimStart([char[]]@('v', 'V'))
if ([string]::IsNullOrWhiteSpace($version)) {
  throw "The update manifest does not contain a valid version."
}

if ([string]::IsNullOrWhiteSpace($ZipPath)) {
  $releaseName = ([string]$manifest.releaseName).Trim()
  if (-not [string]::IsNullOrWhiteSpace($releaseName)) {
    $expectedZip = Join-Path (Join-Path $root "release") ($releaseName + ".zip")
    if (Test-Path -LiteralPath $expectedZip) {
      $ZipPath = $expectedZip
    }
  }
}
if ([string]::IsNullOrWhiteSpace($ZipPath)) {
  throw "Could not identify the public release ZIP from releaseName. Pass -ZipPath explicitly."
}
if (-not $ZipPath -or -not (Test-Path -LiteralPath $ZipPath)) {
  throw "Release ZIP for V$version was not found. Pass -ZipPath explicitly."
}
$ZipPath = [System.IO.Path]::GetFullPath($ZipPath)

$bucket = $BucketUri.Trim().TrimEnd('/')
if (-not $bucket.StartsWith("oss://", [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "BucketUri must use the oss://bucket-name form."
}
$publicBase = $PublicBaseUrl.Trim().TrimEnd('/')
if (-not $publicBase.StartsWith("https://", [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "PublicBaseUrl must be an HTTPS address."
}
$ManifestObject = $ManifestObject.Trim().TrimStart('/')
if ([string]::IsNullOrWhiteSpace($ManifestObject) -or $ManifestObject.Contains('..')) {
  throw "ManifestObject must be a safe relative OSS object path."
}

$assetName = "V$version.zip"
$assetObject = "releases/v$version/$assetName"
if ($isV13Channel) {
  $assetObject = "$ChannelRoot/releases/v$version/$assetName"
}
$assetOssUri = "$bucket/$assetObject"
$manifestOssUri = "$bucket/$ManifestObject"
$assetPublicUrl = "$publicBase/$assetObject"
$githubUrl = ([string]$manifest.downloadUrl).Trim()
if ($githubUrl -notmatch '(?i)github\.com') {
  foreach ($source in @($manifest.downloadUrls)) {
    $candidateUrl = ([string]$source.url).Trim()
    if ($candidateUrl -match '(?i)github\.com') {
      $githubUrl = $candidateUrl
      break
    }
  }
}
$aliyunName = (
  [string][char]0x963F + [string][char]0x91CC + [string][char]0x4E91 +
  [string][char]0x955C + [string][char]0x50CF
)

$downloadSources = @(
  [ordered]@{
    name = $aliyunName
    url = $assetPublicUrl
  }
)
if (-not [string]::IsNullOrWhiteSpace($githubUrl) -and $githubUrl -ne $assetPublicUrl) {
  $downloadSources += [ordered]@{
    name = "GitHub"
    url = $githubUrl
  }
}
$manifest.downloadUrl = $assetPublicUrl
$manifest | Add-Member -NotePropertyName downloadUrls -NotePropertyValue $downloadSources -Force
$manifest.sha256 = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
$manifest.size = (Get-Item -LiteralPath $ZipPath).Length

$scratch = Join-Path $root "scratch\aliyun-mirror"
New-Item -ItemType Directory -Force -Path $scratch | Out-Null
$stagedManifest = Join-Path $scratch "latest.json"
$manifestJson = ($manifest | ConvertTo-Json -Depth 8).Replace("`r`n", "`n")
[System.IO.File]::WriteAllText(
  $stagedManifest,
  $manifestJson.TrimEnd() + "`n",
  [System.Text.UTF8Encoding]::new($false)
)

Write-Host "OSS asset: $assetOssUri"
Write-Host "Public asset: $assetPublicUrl"
Write-Host "OSS manifest: $manifestOssUri"
Write-Host "SHA-256: $($manifest.sha256)"
Write-Host "Size: $($manifest.size)"

if ($DryRun) {
  Write-Host "Dry run: no OSS object was changed."
  Write-Host "Staged manifest: $stagedManifest"
  exit 0
}

if (-not (Get-Command $OssutilPath -ErrorAction SilentlyContinue)) {
  throw "ossutil was not found: $OssutilPath"
}

# Publish immutable asset first.  The manifest is uploaded last so clients
# never discover a release whose ZIP has not finished uploading.
& $OssutilPath cp $ZipPath $assetOssUri -f
if ($LASTEXITCODE -ne 0) {
  throw "Failed to upload the release ZIP to OSS."
}
& $OssutilPath stat $assetOssUri
if ($LASTEXITCODE -ne 0) {
  throw "The uploaded release ZIP could not be verified with ossutil stat."
}
& $OssutilPath cp $stagedManifest $manifestOssUri -f
if ($LASTEXITCODE -ne 0) {
  throw "Failed to upload latest.json to OSS."
}

Copy-Item -LiteralPath $stagedManifest -Destination $ManifestPath -Force
Write-Host "Aliyun OSS mirror published successfully."
Write-Host "Local latest.json updated: $ManifestPath"
