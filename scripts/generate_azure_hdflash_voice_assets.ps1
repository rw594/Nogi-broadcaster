param(
    [string[]]$StemFilter = @()
)

$ErrorActionPreference = "Stop"

$Voice = "zh-CN-Xiaoxiao:DragonHDFlashLatestNeural"
$Style = "voice-assistant"
$VoiceParameters = "temperature=0.35;cfg_scale=1.2"
$OutputFormat = "audio-24khz-48kbitrate-mono-mp3"
$Tempo = "1.35"
$OutputDir = Join-Path (Get-Location) "assets\audio\xiaoyi"
$ScratchDir = Join-Path (Get-Location) "scratch\azure_hdflash_mp3"

$Key = $env:AZURE_SPEECH_KEY
if (-not $Key) {
    $Key = [Environment]::GetEnvironmentVariable("AZURE_SPEECH_KEY", "User")
}
$Region = $env:AZURE_SPEECH_REGION
if (-not $Region) {
    $Region = [Environment]::GetEnvironmentVariable("AZURE_SPEECH_REGION", "User")
}
if (-not $Key) {
    throw "AZURE_SPEECH_KEY is not set."
}
if (-not $Region) {
    throw "AZURE_SPEECH_REGION is not set."
}

$Ffmpeg = python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
if (-not $Ffmpeg) {
    throw "Unable to locate ffmpeg via imageio_ffmpeg."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Force -Path $ScratchDir | Out-Null

$Clips = @(
    @{ Stem = "war_overture_remaining"; Text = "战争序曲" },
    @{ Stem = "war_overture_ended"; Text = "战争序曲，结束" },
    @{ Stem = "lively_song_remaining"; Text = "活跃曲" },
    @{ Stem = "lively_song_ended"; Text = "活跃曲，结束" },
    @{ Stem = "march_song_remaining"; Text = "行进曲"; Voice = "zh-CN-XiaoxiaoNeural"; Style = ""; VoiceParameters = "" },
    @{ Stem = "march_song_ended"; Text = "行进曲，结束"; Voice = "zh-CN-XiaoxiaoNeural"; Style = ""; VoiceParameters = "" },
    @{ Stem = "steadfast_will_remaining"; Text = "坚定意志" },
    @{ Stem = "steadfast_will_ended"; Text = "坚定意志，结束" },
    @{ Stem = "backlight_sword_remaining"; Text = "逆光剑" },
    @{ Stem = "backlight_sword_ended"; Text = "逆光剑，结束" },
    @{ Stem = "deadly_penetration_remaining"; Text = "致命穿透" },
    @{ Stem = "deadly_penetration_ended"; Text = "致命穿透，结束" },
    @{ Stem = "transcend_life_remaining"; Text = "超越生命" },
    @{ Stem = "transcend_life_ended"; Text = "超越生命，结束" },
    @{ Stem = "load_transfer_remaining"; Text = "负载转移" },
    @{ Stem = "load_transfer_ended"; Text = "负载转移，结束" },
    @{ Stem = "demigod_remaining"; Text = "半神化" },
    @{ Stem = "demigod_ended"; Text = "半神 结束" },
    @{ Stem = "demigod_cooldown"; Text = "半神 就绪" },
    @{ Stem = "third_eye_ended"; Text = "三眼 结束" },
    @{ Stem = "third_eye_cooldown"; Text = "三眼 就绪" },
    @{ Stem = "sanctuary_lord_remaining"; Text = "圣域之主" },
    @{ Stem = "sanctuary_lord_ended"; Text = "圣域之主，结束" },
    @{ Stem = "manus_elixir_remaining"; Text = "马纽斯秘药" },
    @{ Stem = "manus_elixir_ended"; Text = "马纽斯秘药，结束" },
    @{ Stem = "purification_wave_remaining"; Text = "净化之浪"; Ssml = "净化之<phoneme alphabet='sapi' ph='lang 4'>浪</phoneme>"; Voice = "zh-CN-XiaoxiaoNeural"; Style = ""; VoiceParameters = "" },
    @{ Stem = "purification_wave_ended"; Text = "净化之浪，结束"; Ssml = "净化之<phoneme alphabet='sapi' ph='lang 4'>浪</phoneme>，结束" },
    @{ Stem = "vitality_song_remaining"; Text = "活力之歌" },
    @{ Stem = "vitality_song_ended"; Text = "活力之歌，结束" },
    @{ Stem = "status_support_remaining"; Text = "状态支援" },
    @{ Stem = "status_support_ended"; Text = "状态支援，结束" },
    @{ Stem = "self_buff_magic_circle_remaining"; Text = "魔法阵" },
    @{ Stem = "self_buff_magic_circle_ended"; Text = "魔法阵 结束" },
    @{ Stem = "self_buff_magic_circle_cooldown"; Text = "魔法阵 就绪" },
    @{ Stem = "festival_food_remaining"; Text = "庆典料理" },
    @{ Stem = "festival_food_ended"; Text = "庆典料理，结束" },
    @{ Stem = "magic_shield_ended"; Text = "魔法盾关闭" },
    @{ Stem = "magic_shield_missing"; Text = "魔法盾忘开啦" },
    @{ Stem = "toah_spirit_progress_remaining"; Text = "托亚灵震爆 即将发生" },
    @{ Stem = "safehouse_warning"; Text = "安全屋" },
    @{ Stem = "boss_mechanic_warning"; Text = "注意机制" },
    @{ Stem = "bu3_red_orb_warning"; Text = "球要炸了" },
    @{ Stem = "laser_warning_prefix"; Text = "激光" },
    @{ Stem = "red_orb_countdown/danger_red_orb"; Text = "危险红球" },
    @{ Stem = "red_orb_countdown/count_05"; Text = "五" },
    @{ Stem = "red_orb_countdown/count_04"; Text = "四" },
    @{ Stem = "red_orb_countdown/count_03"; Text = "三" },
    @{ Stem = "red_orb_countdown/count_02"; Text = "二" },
    @{ Stem = "red_orb_countdown/count_01"; Text = "一" },
    @{ Stem = "red_orb_countdown/count_00"; Text = "零" },
    @{ Stem = "debuffs_ready"; Text = "BUFF齐啦" },
    @{ Stem = "debuffs_renew"; Text = "破防该续啦" },
    @{ Stem = "gunner_eye_remaining"; Text = "枪手之眼" },
    @{ Stem = "gunner_eye_ended"; Text = "枪手之眼，结束" },
    @{ Stem = "astrology"; Text = "占星" },
    @{ Stem = "magic_attack_potion_remaining"; Text = "魔攻水" },
    @{ Stem = "magic_attack_potion_ended"; Text = "魔攻水，结束" },
    @{ Stem = "physical_attack_potion_remaining"; Text = "物攻水" },
    @{ Stem = "physical_attack_potion_ended"; Text = "物攻水，结束" },
    @{ Stem = "magic_cast_speed_potion_remaining"; Text = "法速水" },
    @{ Stem = "magic_cast_speed_potion_ended"; Text = "法速水，结束" },
    @{ Stem = "alchemy_potion_remaining"; Text = "炼金水" },
    @{ Stem = "alchemy_potion_ended"; Text = "炼金水，结束" },
    @{ Stem = "life_temperature_remaining"; Text = "生命的温度" },
    @{ Stem = "life_temperature_ended"; Text = "生命的温度，已褪尽" },
    @{ Stem = "azure_internal_wound_danger"; Text = "湛蓝内伤 达到危险层数" },
    @{ Stem = "azure_internal_wound_cleared"; Text = "湛蓝内伤 已清除" }
)

foreach ($Second in 0..70) {
    $Clips += @{
        Stem = ("safehouse_countdown/safehouse_{0:D2}" -f $Second)
        Text = "安全屋${Second}秒"
    }
}

$Endpoint = "https://$Region.tts.speech.microsoft.com/cognitiveservices/v1"
$Filter = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.03,areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.18,areverse,atempo=$Tempo,loudnorm=I=-18:TP=-1.5:LRA=7,apad=pad_dur=0.10"

foreach ($Clip in $Clips) {
    $Stem = $Clip.Stem
    if ($StemFilter.Count -gt 0 -and $StemFilter -notcontains $Stem) {
        continue
    }
    $Text = $Clip.Text
    $ClipSsml = $Clip.Ssml
    $ClipVoice = $Voice
    if ($Clip.ContainsKey("Voice") -and $Clip.Voice) {
        $ClipVoice = $Clip.Voice
    }
    $ClipStyle = $Style
    if ($Clip.ContainsKey("Style")) {
        $ClipStyle = $Clip.Style
    }
    $ClipVoiceParameters = $VoiceParameters
    if ($Clip.ContainsKey("VoiceParameters")) {
        $ClipVoiceParameters = $Clip.VoiceParameters
    }
    if ($ClipSsml) {
        $Body = $ClipSsml
    } else {
        $Body = [System.Security.SecurityElement]::Escape($Text)
    }
    $VoiceAttributes = "xml:lang='zh-CN' xml:gender='Female' name='$ClipVoice'"
    if ($ClipVoiceParameters) {
        $VoiceAttributes = "$VoiceAttributes parameters='$ClipVoiceParameters'"
    }
    if ($ClipStyle) {
        $VoiceBody = "<mstts:express-as style='$ClipStyle'>$Body</mstts:express-as>"
    } else {
        $VoiceBody = $Body
    }
    $Ssml = @"
<speak version='1.0' xml:lang='zh-CN' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='https://www.w3.org/2001/mstts'>
  <voice $VoiceAttributes>
    $VoiceBody
  </voice>
</speak>
"@
    $Mp3Path = Join-Path $ScratchDir "$Stem.mp3"
    $HeaderPath = Join-Path $ScratchDir "$Stem.headers.txt"
    $WavPath = Join-Path $OutputDir "$Stem.wav"

    foreach ($ParentPath in @(
        (Split-Path -Parent $Mp3Path),
        (Split-Path -Parent $HeaderPath),
        (Split-Path -Parent $WavPath)
    )) {
        if ($ParentPath) {
            New-Item -ItemType Directory -Force -Path $ParentPath | Out-Null
        }
    }

    & curl.exe -sS -D $HeaderPath -o $Mp3Path -X POST $Endpoint `
        -H "Ocp-Apim-Subscription-Key: $Key" `
        -H "Content-Type: application/ssml+xml" `
        -H "X-Microsoft-OutputFormat: $OutputFormat" `
        -H "User-Agent: mabi-buff-watcher-voice-pack" `
        --data-binary $Ssml
    if ($LASTEXITCODE -ne 0) {
        throw "curl failed for $Stem with exit code $LASTEXITCODE."
    }
    $Mp3Item = Get-Item -LiteralPath $Mp3Path
    if ($Mp3Item.Length -lt 1000) {
        $HeaderText = Get-Content -LiteralPath $HeaderPath -Raw
        throw "Azure returned empty audio for $Stem. Headers: $HeaderText"
    }

    $FfmpegOut = Join-Path $ScratchDir "$Stem.ffmpeg.out.txt"
    $FfmpegErr = Join-Path $ScratchDir "$Stem.ffmpeg.err.txt"
    $FfmpegArgs = @("-y", "-i", $Mp3Path, "-af", $Filter, "-ar", "48000", "-ac", "1", $WavPath)
    $FfmpegProcess = Start-Process -FilePath $Ffmpeg -ArgumentList $FfmpegArgs -Wait -PassThru -WindowStyle Hidden -RedirectStandardOutput $FfmpegOut -RedirectStandardError $FfmpegErr
    if ($FfmpegProcess.ExitCode -ne 0) {
        $FfmpegError = Get-Content -LiteralPath $FfmpegErr -Raw
        throw "ffmpeg failed for $Stem with exit code $($FfmpegProcess.ExitCode). $FfmpegError"
    }
    Write-Host "$WavPath <- $Text"
}
