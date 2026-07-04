from __future__ import annotations

from pathlib import Path
import math
import wave


SAMPLE_RATE = 44_100


def tone(frequency: float, seconds: float, volume: float = 0.28) -> list[int]:
    frames = int(SAMPLE_RATE * seconds)
    fade_frames = max(1, min(int(SAMPLE_RATE * 0.018), frames // 2))
    samples: list[int] = []
    for index in range(frames):
        envelope = 1.0
        if index < fade_frames:
            envelope = index / fade_frames
        elif index >= frames - fade_frames:
            envelope = (frames - index - 1) / fade_frames
        value = math.sin(2 * math.pi * frequency * index / SAMPLE_RATE)
        samples.append(int(32767 * volume * envelope * value))
    return samples


def silence(seconds: float) -> list[int]:
    return [0] * int(SAMPLE_RATE * seconds)


def write_wav(path: Path, samples: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(SAMPLE_RATE)
        stream.writeframes(b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples))


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "assets" / "audio"
    write_wav(root / "warn.wav", tone(523.25, 0.16) + silence(0.06) + tone(783.99, 0.24))
    write_wav(root / "critical.wav", tone(587.33, 0.12) + silence(0.04) + tone(880.00, 0.16) + silence(0.04) + tone(1174.66, 0.22))
    write_wav(root / "ended.wav", tone(783.99, 0.14) + silence(0.06) + tone(392.00, 0.30))
    print(f"wrote placeholder audio to {root}")


if __name__ == "__main__":
    main()
