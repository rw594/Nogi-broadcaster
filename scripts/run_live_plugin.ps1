param(
  [string]$Histories = "C:\Users\rw594\Desktop\MicoPunch\histories",

  [string]$Config = "buffwatcher.config.local.json",

  [ValidateSet("websocket", "file")]
  [string]$Source = "websocket",

  [string]$HostName = "127.0.0.1",

  [int]$Port = 18000,

  [string]$Path = "/ws",

  [string]$SelfId = "",

  [switch]$NoAudio,

  [switch]$NoSelfFilter,

  [switch]$PlayExisting,

  [switch]$NoBell,

  [switch]$VerboseEvents,

  [switch]$AllowMultiple,

  [double]$PollSeconds = 0.5,

  [double]$IdleReconnectSeconds = 0,

  [double]$StatusInterval = 30,

  [double]$MaxSeconds = 0
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
$env:PYTHONDONTWRITEBYTECODE = "1"

if (-not $AllowMultiple) {
  $existing = Get-CimInstance Win32_Process |
    Where-Object {
      $_.Name -eq "python.exe" -and
      $_.CommandLine -match "buffwatcher\.live"
    }

  foreach ($process in $existing) {
    Stop-Process -Id $process.ProcessId -Force
    Write-Host "[live] stopped existing watcher pid $($process.ProcessId)"
  }
}

$argsList = @(
  "-m", "buffwatcher.live",
  "--source", $Source,
  "--histories", $Histories,
  "--config", $Config,
  "--host", $HostName,
  "--port", "$Port",
  "--path", $Path,
  "--poll-seconds", "$PollSeconds",
  "--idle-reconnect-seconds", "$IdleReconnectSeconds",
  "--status-interval", "$StatusInterval",
  "--max-seconds", "$MaxSeconds"
)

if ($SelfId) { $argsList += @("--self-id", $SelfId) }
if ($NoAudio) { $argsList += "--no-audio" }
if ($NoSelfFilter) { $argsList += "--no-self-filter" }
if ($PlayExisting) { $argsList += "--play-existing" }
if ($NoBell) { $argsList += "--no-bell" }
if ($VerboseEvents) { $argsList += "--verbose-events" }

python @argsList
exit $LASTEXITCODE
