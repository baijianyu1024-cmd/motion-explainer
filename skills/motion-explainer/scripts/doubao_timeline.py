"""Build shot times and short subtitle cues from the Doubao word timestamps."""
import argparse
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def aligned_indices(src, ref):
    mapping = [None] * len(src)
    for a, b, size in SequenceMatcher(None, src, ref, autojunk=False).get_matching_blocks():
        mapping[a:a + size] = range(b, b + size)
    return mapping


def char_width(text):
    return sum(1 if unicodedata.east_asian_width(c) in "WF" else .55 for c in text)


def caption_chunks(text):
    # Group small phrases to avoid flashing a separate subtitle for a short lead-in.
    phrases = re.findall(r"[^，。！？；：、,!?;:]+[，。！？；：、,!?;:]*", text)
    groups = []
    current = ""
    for p in phrases:
        if current and (current.rstrip().endswith(("。", "！", "？", "!", "?")) or char_width(current + p) > (27 if char_width(current) < 6 else 23)):
            groups.append(current.strip())
            current = ""
        current += p
    if current.strip():
        groups.append(current.strip())
    return groups or [text]


def timecode(seconds):
    ms = round(seconds * 1000)
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"


def run(root):
    audio = root / "doubao.mp3"
    metadata = json.loads((root / "doubao.mp3.doubao.json").read_text())
    if metadata.get("audioSha256") and hashlib.sha256(audio.read_bytes()).hexdigest() != metadata["audioSha256"]:
        raise ValueError("Timestamps belong to a different MP3.")
    duration = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(audio)], text=True).strip())
    cues = json.loads((root / "cues.json").read_text())
    if not cues or not metadata["sentences"]:
        raise ValueError("Nonempty time-stamped speech and script cues are required.")
    words = [w for s in metadata["sentences"] for w in s["words"] if normalize(w["word"])]
    if not words or any(not 0 <= w["startTime"] <= w["endTime"] <= duration + .2 for w in words):
        raise ValueError("Invalid speech timestamps.")
    reference, word_for_char = [], []
    for i, w in enumerate(words):
        tokens = normalize(w["word"])
        reference.append(tokens)
        word_for_char.extend([i] * len(tokens))
    spoken = [normalize(c["spoken"]) for c in cues]
    matched = aligned_indices("".join(spoken), "".join(reference))
    lines, captions = [], []
    cursor = 0

    def span(indices):
        ids = [word_for_char[i] for i in indices if i is not None]
        if not ids:
            raise ValueError("No timestamped words match this cue.")
        return max(0., words[ids[0]]["startTime"]), min(duration, words[ids[-1]]["endTime"])

    for no, (cue, script) in enumerate(zip(cues, spoken), 1):
        cue_indices = matched[cursor:cursor + len(script)]
        cursor += len(script)
        verified = sum(i is not None for i in cue_indices)
        if verified < .7 * len(script) or not script:
            raise ValueError(f"Review cue {no}: {verified}/{len(script)} spoken characters matched.")
        start, end = span(cue_indices)
        body = cue["caption"].strip()
        lines.append(dict(start=start, end=end, text=body))
        chunks = caption_chunks(body)
        parts = [normalize(c) for c in chunks]
        caption_to_spoken = aligned_indices("".join(parts), script)
        offset = 0
        entries = []
        for chunk, norm in zip(chunks, parts):
            selected = [cue_indices[i] for i in caption_to_spoken[offset:offset+len(norm)] if i is not None]
            offset += len(norm)
            if not any(i is not None for i in selected):
                # An entirely rephrased caption still belongs to the verified full scene.
                entries = [dict(start=start, end=end, text=body)]
                break
            left, right = span(selected)
            entries.append(dict(start=left, end=right, text=chunk))
        entries[0]["start"], entries[-1]["end"] = start, end
        captions.extend(entries)
        print(f"{no:2}  {start:6.3f} – {end:6.3f} s   {verified}/{len(script)} matched")
    for rows in (lines, captions):
        if any(r["end"] <= r["start"] for r in rows):
            raise ValueError("A cue has zero or negative duration.")
        for a, b in zip(rows, rows[1:]):
            if a["end"] > b["start"] + .04:
                raise ValueError("Overlapping timestamps: inspect cue boundaries before rendering.")
            a["end"] = min(a["end"], b["start"])
    (root / "timeline.json").write_text(json.dumps(dict(duration=duration, lines=lines, captions=captions),
                     ensure_ascii=False, indent=2) + "\n")
    text = "\n\n".join(f"{i}\n{timecode(c['start'])} --> {timecode(c['end'])}\n{c['text']}"
                       for i, c in enumerate(captions, 1))
    (root / "subtitles.srt").write_text(text + "\n")
    print(f"{len(lines)} scene cues, {len(captions)} subtitle cues, {duration:.3f} seconds.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True, help="Episode folder containing cues.json")
    parser.add_argument("--prepare", action="store_true", help="Write narration.txt from the spoken cues before synthesis")
    args = parser.parse_args()
    if args.prepare:
        cues = json.loads((args.dir / "cues.json").read_text(encoding="utf-8"))
        if not cues or any(not cue.get("spoken", "").strip() or not cue.get("caption", "").strip() for cue in cues):
            parser.error("Each cue needs nonempty spoken and caption text.")
        (args.dir / "narration.txt").write_text("\n".join(cue["spoken"].strip() for cue in cues) + "\n", encoding="utf-8")
    else:
        run(args.dir)
