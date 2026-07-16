from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg


VOICE = "zh-CN-XiaoyiNeural"
RATE = "+24%"
PITCH = "-18Hz"

OUTPUT_DIR = Path("assets/audio/xiaoyi")
SCRATCH_DIR = Path("scratch/xiaoyi_mp3")

FFMPEG_FILTER = (
    "silenceremove="
    "start_periods=1:start_threshold=-50dB:start_silence=0.03,"
    "areverse,"
    "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.18,"
    "areverse,"
    "loudnorm=I=-18:TP=-1.5:LRA=7,"
    "apad=pad_dur=0.12"
)


CLIPS = [
    ("war_overture_remaining", "战争序曲"),
    ("war_overture_ended", "战争序曲，结束"),
    ("lively_song_remaining", "活跃曲"),
    ("lively_song_ended", "活跃曲，结束"),
    ("march_song_remaining", "行进曲"),
    ("march_song_ended", "行进曲，结束"),
    ("steadfast_will_remaining", "坚定意志"),
    ("steadfast_will_ended", "坚定意志，结束"),
    ("backlight_sword_remaining", "逆光剑"),
    ("backlight_sword_ended", "逆光剑，结束"),
    ("deadly_penetration_remaining", "致命穿透"),
    ("deadly_penetration_ended", "致命穿透，结束"),
    ("transcend_life_remaining", "超越生命"),
    ("transcend_life_ended", "超越生命，结束"),
    ("load_transfer_remaining", "负载转移"),
    ("load_transfer_ended", "负载转移，结束"),
    ("demigod_remaining", "半神化"),
    ("demigod_ended", "半神 结束"),
    ("demigod_cooldown", "半神 就绪"),
    ("third_eye_ended", "三眼 结束"),
    ("third_eye_cooldown", "三眼 就绪"),
    ("sanctuary_lord_remaining", "圣域之主"),
    ("sanctuary_lord_ended", "圣域之主，结束"),
    ("manus_elixir_remaining", "马纽斯秘药"),
    ("manus_elixir_ended", "马纽斯秘药，结束"),
    ("purification_wave_remaining", "净化之浪"),
    ("purification_wave_ended", "净化之浪，结束"),
    # Use 孰 as a pronunciation-safe homophone for 熟 (shú) in the Edge-TTS fallback.
    ("hamster_supercharged_remaining", "鼠孰"),
    ("hamster_supercharged_ended", "鼠熟，已去世"),
    ("hamster_adrenaline_remaining", "鼠熟回血"),
    ("hamster_adrenaline_ended", "鼠熟回血，结束"),
    ("vitality_song_remaining", "活力之歌"),
    ("vitality_song_ended", "活力之歌，结束"),
    ("status_support_remaining", "状态支援"),
    ("status_support_ended", "状态支援，结束"),
    ("self_buff_magic_circle_remaining", "魔法阵"),
    ("self_buff_magic_circle_ended", "魔法阵 结束"),
    ("self_buff_magic_circle_cooldown", "魔法阵 就绪"),
    ("festival_food_remaining", "庆典料理"),
    ("festival_food_ended", "庆典料理，结束"),
    ("magic_shield_ended", "魔法盾关闭"),
    ("magic_shield_missing", "魔法盾忘开啦"),
    ("toah_spirit_progress_remaining", "托亚灵震爆 即将发生"),
    ("safehouse_warning", "安全屋"),
    ("boss_mechanic_warning", "注意机制"),
    ("magic_attack_potion_remaining", "魔攻水"),
    ("magic_attack_potion_ended", "魔攻水，结束"),
    ("physical_attack_potion_remaining", "物攻水"),
    ("physical_attack_potion_ended", "物攻水，结束"),
    ("magic_cast_speed_potion_remaining", "法速水"),
    ("magic_cast_speed_potion_ended", "法速水，结束"),
    ("alchemy_potion_remaining", "炼金水"),
    ("alchemy_potion_ended", "炼金水，结束"),
    ("life_temperature_remaining", "生命的温度"),
    ("life_temperature_ended", "生命的温度，已褪尽"),
    ("azure_internal_wound_danger", "湛蓝内伤 达到危险层数"),
    ("azure_internal_wound_cleared", "湛蓝内伤 已清除"),
]


async def synthesize_clip(stem: str, text: str) -> Path:
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    mp3_path = SCRATCH_DIR / f"{stem}.mp3"
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(str(mp3_path))
    return mp3_path


def convert_to_wav(mp3_path: Path, wav_path: Path) -> None:
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(mp3_path),
            "-af",
            FFMPEG_FILTER,
            "-ar",
            "48000",
            "-ac",
            "1",
            str(wav_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


async def main() -> None:
    for stem, text in CLIPS:
        mp3_path = await synthesize_clip(stem, text)
        wav_path = OUTPUT_DIR / f"{stem}.wav"
        convert_to_wav(mp3_path, wav_path)
        print(f"{wav_path.as_posix()} <- {text}")


if __name__ == "__main__":
    asyncio.run(main())
