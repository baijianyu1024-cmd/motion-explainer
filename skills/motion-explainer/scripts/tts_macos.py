"""Use an installed macOS voice to record one file per narration cue."""
import argparse
from array import array
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(
        description="Create local speech clips and a manifest for align.py with macOS say and FFmpeg.",
        epilog='Input example: [{"text":"先看这张图。","pause":0.4}]. Pause is in seconds. '
               'List installed voices with say -v "?". Other platforms can feed recorded clips to align.py.'
    )
    parser.add_argument("cues", type=Path)
    parser.add_argument("output", type=Path, help="New directory for the clips and manifest")
    parser.add_argument("--voice", default="Tingting", help="Installed macOS voice (default: Tingting)")
    parser.add_argument("--rate", type=int, default=195, help="Speaking rate for say (default: 195)")
    args = parser.parse_args()
    if sys.platform != "darwin" or not shutil.which("say") or not shutil.which("ffmpeg"):
        parser.error("This synthesizer requires macOS, say, and FFmpeg.")
    if args.rate <= 0 or args.output.exists():
        parser.error("Choose a positive rate and a new output directory.")
    cues = json.loads(args.cues.read_text(encoding="utf-8"))
    if not isinstance(cues, list) or not cues:
        parser.error("Expected a nonempty list of cue objects.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent) as temp:
        stage = Path(temp) / "clips"
        stage.mkdir()
        manifest = []
        for i, cue in enumerate(cues, 1):
            if not isinstance(cue, dict) or not isinstance(cue.get("text"), str) or not cue["text"].strip():
                parser.error(f"Cue {i} needs nonempty text.")
            text = cue["text"].strip()
            pause = cue.get("pause", 0)
            if not isinstance(pause, (int, float)) or not math.isfinite(pause) or pause < 0:
                parser.error(f"Cue {i} needs a nonnegative finite pause.")
            clip = stage / f"line-{i:03}.aiff"
            subprocess.run(["say", "-v", args.voice, "-r", str(args.rate), "-o", str(clip),
                            "-f", "-"], input=text, encoding="utf-8", check=True)
            pcm = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(clip), "-map", "0:a:0",
                                           "-ar", "8000", "-ac", "1", "-f", "s16le", "-"])
            samples = array("h", pcm)
            if max(map(abs, samples), default=0) < 128:
                parser.error(f"Cue {i} produced silent audio. Check access to the local macOS speech service.")
            manifest.append({"text": text, "file": clip.name, "pause": pause})
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        stage.rename(args.output)
    print(args.output / "manifest.json")


if __name__ == "__main__":
    main()
