"""Make a self-contained, seekable HTML film from timed narration and source figures."""
import argparse
import base64
import json
import math
from pathlib import Path


def data_url(path, mime):
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def region(box):
    if not isinstance(box, list) or len(box) != 4:
        raise ValueError("A region must contain [left, top, right, bottom].")
    x, y, r, b = box
    if not (0 <= x < r <= 1 and 0 <= y < b <= 1):
        raise ValueError(f"Region outside original image: {box}")
    return box


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="JSON shot plan; file paths relative to this file")
    parser.add_argument("timeline", type=Path, help="timeline.json from align.py or doubao_timeline.py")
    parser.add_argument("html", type=Path)
    parser.add_argument("--audio", type=Path, help="Optional M4A/AAC, MP3 or WAV for in-browser playback")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    timeline = json.loads(args.timeline.read_text(encoding="utf-8"))
    image_mimes = {".png":"image/png", ".jpg":"image/jpeg", ".jpeg":"image/jpeg", ".webp":"image/webp"}
    figures = {}
    for key, fig in plan["figures"].items():
        source = args.plan.parent / fig["file"]
        mime = image_mimes.get(source.suffix.lower())
        if not mime:
            parser.error(f"Use a PNG, JPEG or WebP for figure {key}.")
        figures[key] = {"src": data_url(source, mime), "label": fig["label"]}
    shots = []
    previous = -1
    for shot in plan["shots"]:
        cue = shot["cue"]
        if not isinstance(cue, int) or not 1 <= cue <= len(timeline["lines"]):
            parser.error(f"Unknown 1-based cue number {cue}.")
        if shot["figure"] not in figures:
            parser.error(f"Unknown figure {shot['figure']}.")
        start = timeline["lines"][cue-1]["start"] + shot.get("offset", 0)
        if not shots and cue == 1 and shot.get("offset", 0) == 0:
            start = 0  # Show the opening picture during any silence before the first word.
        if not math.isfinite(start) or not 0 <= start < timeline["duration"] or start <= previous:
            parser.error("Shot times must increase within the timeline.")
        previous = start
        shots.append(dict(start=start, title=shot["title"], figure=shot["figure"],
                          view=region(shot.get("view", [0,0,1,1])),
                          mark=region(shot["mark"]) if shot.get("mark") else None))
    if not shots or shots[0]["start"] != 0:
        parser.error("The first shot must start at 0.")
    film = dict(title=plan["title"], byline=plan.get("byline", ""), figures=figures, shots=shots, **timeline)
    if args.audio:
        types = {".mp3":"audio/mpeg", ".wav":"audio/wav", ".m4a":"audio/mp4", ".aac":"audio/aac"}
        mime = types.get(args.audio.suffix.lower())
        if not mime:
            parser.error("Preview audio must be WAV, MP3, AAC or M4A.")
        film["audio"] = data_url(args.audio, mime)
    template = Path(__file__).resolve().parents[1]/"assets"/"figure-stage.html"
    encoded = json.dumps(film, ensure_ascii=False, allow_nan=False).replace("<", r"\u003c")
    args.html.write_text(template.read_text(encoding="utf-8").replace("/* FILM_DATA */ null", encoded), encoding="utf-8")


if __name__ == "__main__":
    main()
