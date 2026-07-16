param(
  [Parameter(Mandatory=$true)][string]$BucketUri,
  [Parameter(Mandatory=$true)][string]$PublicBaseUrl,
  [string]$OssutilPath = "ossutil",
  [string]$Version = "",
  [int]$Revision = 0,
  [string[]]$Notes = @(),
  [string]$ManifestObject = "visual/v2/latest.json",
  [string]$ChannelRoot = "",
  [string]$UpdateChannelId = "nogi-v13-visual",
  [switch]$SkipProjectFolderCopy,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$ChannelRoot = $ChannelRoot.Trim().Trim('/')
$isV13Channel = $ChannelRoot -eq "channels/v13/visual"
$updateDisableFlag = Join-Path $root "AUTO_UPDATE_DISABLED"
if ((Test-Path -LiteralPath $updateDisableFlag) -and -not $isV13Channel) {
  throw "Automatic update publishing is disabled by AUTO_UPDATE_DISABLED. Audit and fix the updater before removing the block."
}
if ($isV13Channel -and $ManifestObject.Trim().TrimStart('/') -ne "channels/v13/visual/latest.json") {
  throw "The V1.3 visual channel can only publish channels/v13/visual/latest.json."
}
if ($isV13Channel -and $UpdateChannelId -ne "nogi-v13-visual") {
  throw "The V1.3 visual channel requires UpdateChannelId=nogi-v13-visual."
}

if ([string]::IsNullOrWhiteSpace($Version)) {
  $publicLatest = [System.IO.File]::ReadAllText(
    (Join-Path $root "latest.json"),
    [System.Text.Encoding]::UTF8
  ) | ConvertFrom-Json
  $Version = [string]$publicLatest.version
}
$Version = $Version.Trim().TrimStart([char[]]@('v', 'V'))
if ([string]::IsNullOrWhiteSpace($Version)) {
  throw "Could not determine the visual build version."
}

$parsedVersion = [regex]::Match(
  $Version,
  '^(?<major>\d+)\.(?<minor>\d+)(?:\.(?<patch>\d+))?(?<suffix>[A-Za-z])?$'
)
if (-not $parsedVersion.Success) {
  throw "Could not calculate a version code from: $Version"
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

$bucket = $BucketUri.Trim().TrimEnd('/')
if (-not $bucket.StartsWith("oss://", [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "BucketUri must use the oss://bucket-name form."
}
$publicBase = $PublicBaseUrl.Trim().TrimEnd('/')
if (-not $publicBase.StartsWith("https://", [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "PublicBaseUrl must be an HTTPS address."
}
$manifestObject = $ManifestObject.Trim().TrimStart('/')
if ([string]::IsNullOrWhiteSpace($manifestObject) -or $manifestObject.Contains('..')) {
  throw "ManifestObject must be a safe relative OSS object path."
}
$manifestPublicUrl = "$publicBase/$manifestObject"

if ($Revision -eq 0) {
  $Revision = 1
  try {
    $cacheBust = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $previous = Invoke-RestMethod -Uri ($manifestPublicUrl + "?t=" + $cacheBust) -TimeoutSec 10
    if (([string]$previous.baseVersion).Trim() -eq $Version) {
      $Revision = ([int]$previous.visualRevision) + 1
    }
  } catch {
    Write-Host "No previous visual manifest was found; starting at revision 1."
  }
}
if ($Revision -lt 1 -or $Revision -gt 99) {
  throw "Revision must be between 1 and 99."
}
$visualVersionCode = ($baseVersionCode * 100) + $Revision

$buildArguments = @{
  Version = $Version
  VisualRevision = $Revision
  VisualUpdateMetadataUrl = $manifestPublicUrl
  UpdateChannelId = $UpdateChannelId
  SkipProjectFolderCopy = $SkipProjectFolderCopy
}
& scripts\build_visual_private.ps1 @buildArguments
if ($LASTEXITCODE -ne 0) {
  throw "The visual private build failed."
}

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
$releaseName = ($productName + " V" + $Version + " " + $visualLabel)
$releaseRoot = Join-Path $root "release"
$zipPath = Join-Path $releaseRoot ($releaseName + ".zip")
$packageInfoPath = Join-Path (
  Join-Path (Join-Path $releaseRoot $releaseName) $runtimeDirName
) "package-info.json"
if (-not (Test-Path -LiteralPath $zipPath)) {
  throw "Visual ZIP was not found: $zipPath"
}
if (-not (Test-Path -LiteralPath $packageInfoPath)) {
  throw "Visual package-info.json was not found: $packageInfoPath"
}
$packageInfo = [System.IO.File]::ReadAllText(
  $packageInfoPath,
  [System.Text.Encoding]::UTF8
) | ConvertFrom-Json
if ([int]$packageInfo.version_code -ne $visualVersionCode) {
  throw "Visual package version code does not match the deployment revision."
}
if (-not (@($packageInfo.update_urls) -contains $manifestPublicUrl)) {
  throw "Visual package does not contain its private update manifest URL."
}

$assetName = "V$Version-visual-r$Revision.zip"
$assetObject = "visual/releases/v$Version/r$Revision/$assetName"
if ($isV13Channel) {
  $assetObject = "$ChannelRoot/releases/v$Version/r$Revision/$assetName"
}
$assetOssUri = "$bucket/$assetObject"
$assetPublicUrl = "$publicBase/$assetObject"
$manifestOssUri = "$bucket/$manifestObject"
$sha256 = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
$size = (Get-Item -LiteralPath $zipPath).Length
if ($Notes.Count -eq 0) {
  $Notes = @("Visual private build feature and stability update.")
}
$aliyunName = (
  [string][char]0x963F + [string][char]0x91CC + [string][char]0x4E91 +
  [string][char]0x955C + [string][char]0x50CF
)
$manifest = [ordered]@{
  app = $productName
  channel = $UpdateChannelId
  version = ($Version + "-visual." + $Revision)
  baseVersion = $Version
  visualRevision = $Revision
  versionCode = $visualVersionCode
  releaseName = $releaseName
  publishedAt = (Get-Date -Format "yyyy-MM-dd")
  downloadUrl = $assetPublicUrl
  sha256 = $sha256
  size = $size
  mandatory = $false
  notes = @($Notes)
  downloadUrls = @(
    [ordered]@{
      name = $aliyunName
      url = $assetPublicUrl
    }
  )
}

$scratch = Join-Path $root "scratch\visual-private\deploy"
New-Item -ItemType Directory -Force -Path $scratch | Out-Null
$manifestPath = Join-Path $scratch "latest.json"
$manifestJson = ($manifest | ConvertTo-Json -Depth 8).Replace("`r`n", "`n")
[System.IO.File]::WriteAllText(
  $manifestPath,
  $manifestJson.TrimEnd() + "`n",
  [System.Text.UTF8Encoding]::new($false)
)

Write-Host ("Visual revision: " + $Revision)
Write-Host ("Visual version code: " + $visualVersionCode)
Write-Host ("OSS asset: " + $assetOssUri)
Write-Host ("Public asset: " + $assetPublicUrl)
Write-Host ("OSS manifest: " + $manifestOssUri)
Write-Host ("SHA-256: " + $sha256)
Write-Host ("Size: " + $size)

if ($DryRun) {
  Write-Host ("Dry run: staged manifest: " + $manifestPath)
  exit 0
}
if (-not (Get-Command $OssutilPath -ErrorAction SilentlyContinue)) {
  throw "ossutil was not found: $OssutilPath"
}

# Upload the immutable package first. Publish the mutable manifest last so
# clients never discover an incomplete release.
& $OssutilPath cp $zipPath $assetOssUri -f
if ($LASTEXITCODE -ne 0) {
  throw "Failed to upload the visual ZIP to OSS."
}
& $OssutilPath stat $assetOssUri
if ($LASTEXITCODE -ne 0) {
  throw "The uploaded visual ZIP could not be verified with ossutil stat."
}
& $OssutilPath cp $manifestPath $manifestOssUri -f
if ($LASTEXITCODE -ne 0) {
  throw "Failed to upload the visual update manifest to OSS."
}

Write-Host "Visual private update channel published successfully."
