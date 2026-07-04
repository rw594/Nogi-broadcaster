param(
  [ValidateSet("list", "sounds", "replay")]
  [string]$Mode = "replay",

  [string]$Histories = "C:\Users\rw594\Desktop\MicoPunch\histories",

  [string]$File = "",

  [switch]$NoAudio,

  [switch]$NoSleep,

  [switch]$Drain
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
$env:PYTHONDONTWRITEBYTECODE = "1"

if ($Mode -eq "list") {
  python -m buffwatcher.alerting list-enabled
  exit $LASTEXITCODE
}

if ($Mode -eq "sounds") {
  $argsList = @("-m", "buffwatcher.alerting", "test-sounds")
  if ($NoAudio) { $argsList += "--no-audio" }
  python @argsList
  exit $LASTEXITCODE
}

$replayArgs = @("-m", "buffwatcher.alerting", "replay")
if ($File) {
  $replayArgs += @("--file", $File)
} else {
  $replayArgs += @("--histories", $Histories)
}
if ($NoAudio) { $replayArgs += "--no-audio" }
if ($NoSleep) { $replayArgs += "--no-sleep" }
if ($Drain) { $replayArgs += "--drain" }

python @replayArgs
exit $LASTEXITCODE
