"""Build a narration track and matching subtitle / timeline files from recorded lines."""
import argparse
import json
import math
import subprocess
import tempfile
import wave
from pathlib import Path

RATE = 48000


def srt_time(seconds):
    millis = round(seconds * 1000)
    return f"{millis//3600000:02}:{millis//60000%60:02}:{millis//1000%60:02},{millis%1000:03}"


def main():
    parser = argparse.ArgumentParser(
        description="Combine recorded lines and pauses into narration.wav, timeline.json and subtitles.srt.",
        epilog='JSON example: [{"text":"同一笔订单只算一次。","file":"line-01.wav","pause":0.4}]. '
               'File paths are relative to the JSON. Pause is silence after each line, in seconds.'
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    lines = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(lines, list) or not lines:
        parser.error("Provide a nonempty list of recorded lines.")
    args.output.mkdir(parents=True, exist_ok=True)
    cues, captions = [], []
    sample = 0
    with tempfile.TemporaryDirectory(dir=args.output) as temp:
        stage = Path(temp)
        with wave.open(str(stage / "narration.wav"), "wb") as audio:
            audio.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            for i, item in enumerate(lines, start=1):
                text = item["text"].strip()
                source = args.manifest.parent / item["file"]
                gap = float(item.get("pause", 0))
                if not text or not math.isfinite(gap) or gap < 0:
                    parser.error(f"Line {i} needs text and a nonnegative finite pause.")
                pcm = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(source),
                    "-map", "0:a:0", "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"])
                if not pcm:
                    parser.error(f"Line {i} has no audio samples.")
                start = sample / RATE
                sample += len(pcm) // 2
                end = sample / RATE
                audio.writeframesraw(pcm)
                silence = round(gap * RATE)
                audio.writeframesraw(bytes(2 * silence))
                sample += silence
                cues.append(dict(text=text, start=start, end=end))
                captions.append(f"{i}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n")
        (stage / "timeline.json").write_text(
            json.dumps(dict(duration=sample/RATE, lines=cues), ensure_ascii=False, indent=2), encoding="utf-8")
        (stage / "subtitles.srt").write_text("\n".join(captions), encoding="utf-8")
        for name in ("narration.wav", "timeline.json", "subtitles.srt"):
            (stage / name).replace(args.output / name)


if __name__ == "__main__":
    main()
