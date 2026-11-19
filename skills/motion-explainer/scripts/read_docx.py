#!/usr/bin/env python3
"""Extract ordered body text and original embedded images from a local DOCX."""
import argparse
import hashlib
import json
import mimetypes
import posixpath
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from zipfile import BadZipFile, ZipFile


def local(name):
    return name.rsplit("}", 1)[-1]


def attr(element, name, default=""):
    return next((v for k, v in element.attrib.items() if local(k) == name), default)


def elements(element, name):
    return (node for node in element.iter() if local(node.tag) == name)


def package_path(part, target):
    target = unquote(target)
    url = urlsplit(target)
    if url.scheme or url.netloc or url.query or url.fragment or "\\" in target:
        raise ValueError(f"Unsupported package reference {target!r}")
    path = posixpath.normpath(posixpath.join(posixpath.dirname(part), target)).lstrip("/")
    if not path or path == ".." or path.startswith("../"):
        raise ValueError(f"Invalid package reference {target!r}")
    return path


def relationships(archive, part):
    path = PurePosixPath(part)
    name = str(path.parent / "_rels" / (path.name + ".rels")) if part else "_rels/.rels"
    if name not in archive.namelist():
        return {}
    root = ET.fromstring(archive.read(name))
    return {node.get("Id"): node.attrib for node in root}


def child_relationship(archive, rels, parent, kind, default):
    for rel in rels.values():
        if rel.get("Type", "").endswith("/" + kind):
            if rel.get("TargetMode") == "External":
                raise ValueError(f"The {kind} part is external.")
            return package_path(parent, rel["Target"])
    return default


def compatible_children(element):
    if local(element.tag) == "AlternateContent":
        options = list(element)
        # Prefer an embedded picture branch, including a raster fallback for native drawings.
        for option in options:
            if any(local(n.tag) in {"blip", "imagedata"} for n in option.iter()):
                return [option]
        return options[:1]
    return list(element)


def extract(source, stage):
    assets, blocks, warnings = [], [], []
    image_ids = {}
    table_count = 0

    with ZipFile(source) as archive:
        body_part = child_relationship(archive, relationships(archive, ""), "", "officeDocument", "word/document.xml")
        root = ET.fromstring(archive.read(body_part))
        body = next(elements(root, "body"), None)
        if body is None:
            raise ValueError("The document has no Word body.")
        rels = relationships(archive, body_part)
        types = ET.fromstring(archive.read("[Content_Types].xml"))
        defaults = {n.get("Extension", "").lower(): n.get("ContentType") for n in types if local(n.tag) == "Default"}
        overrides = {unquote(n.get("PartName", "")).lstrip("/"): n.get("ContentType") for n in types if local(n.tag) == "Override"}
        style_part = child_relationship(archive, rels, body_part, "styles", "")
        styles = {}
        if style_part:
            for style in elements(ET.fromstring(archive.read(style_part)), "style"):
                name = next(elements(style, "name"), None)
                if name is not None:
                    styles[attr(style, "styleId")] = attr(name, "val")

        def image_asset(rid):
            rel = rels.get(rid, {})
            if rel.get("TargetMode") == "External":
                raise ValueError("Externally linked picture; use the document preview or provide the original.")
            if not rel.get("Type", "").endswith("/image"):
                raise ValueError(f"Missing embedded image relationship {rid!r}.")
            part = package_path(body_part, rel["Target"])
            if part in image_ids:
                return image_ids[part]
            if part not in archive.namelist():
                raise ValueError(f"Image part {part!r} is missing.")
            ext = PurePosixPath(part).suffix.lower()
            mime = overrides.get(part) or defaults.get(ext.lstrip(".")) or mimetypes.guess_type(part)[0]
            if not mime or not mime.startswith("image/"):
                raise ValueError(f"Cannot identify image type for {part!r}.")
            if ext not in {".png", ".jpeg", ".jpg", ".webp", ".gif", ".bmp", ".tiff", ".tif", ".emf", ".wmf", ".svg", ".avif", ".heic"}:
                ext = ".img"
            asset_id = f"img{len(assets)+1:03d}"
            temp = stage / (asset_id + ".part")
            digest = hashlib.sha256()
            with archive.open(part) as src, temp.open("wb") as dst:
                while chunk := src.read(256 * 1024):
                    dst.write(chunk)
                    digest.update(chunk)
            # Content-based names let a rerun publish its refreshed manifest last.
            relative = f"media/{asset_id}-{digest.hexdigest()[:16]}{ext}"
            temp.rename(stage / relative)
            assets.append(dict(id=asset_id, path=relative, content_type=mime, source_part=part))
            image_ids[part] = asset_id
            return asset_id

        def read_paragraph(node, table_path):
            block_id = f"p{len(blocks)+1:04d}"
            parts = []

            def note(reason):
                warnings.append(f"{block_id}: {reason}")
                parts.append(dict(type="unresolved", reason=reason))

            def add_text(text):
                if parts and parts[-1]["type"] == "text":
                    parts[-1]["text"] += text
                else:
                    parts.append(dict(type="text", text=text))

            def visit(el, alt="", floating=False, crop=None):
                tag = local(el.tag)
                if tag in {"del", "moveFrom", "pPr", "rPr", "instrText", "delText"}:
                    return
                if tag == "t":
                    add_text(el.text or "")
                    return
                if tag in {"br", "cr", "tab"}:
                    add_text("\t" if tag == "tab" else "\n")
                    return
                if tag in {"drawing", "pict"}:
                    desc = next(elements(el, "docPr"), None)
                    if desc is not None:
                        alt = attr(desc, "descr") or attr(desc, "title")
                    floating = next(elements(el, "anchor"), None) is not None
                    if not any(local(n.tag) in {"blip", "imagedata"} for n in el.iter()):
                        note("Native drawing or text box; inspect its rendered page.")
                if tag == "blipFill":
                    rect = next(elements(el, "srcRect"), None)
                    crop = {k: attr(rect, k) for k in ("l", "t", "r", "b") if attr(rect, k)} if rect is not None else {}
                if tag in {"blip", "imagedata"}:
                    rid = attr(el, "embed") or attr(el, "id") or attr(el, "link")
                    try:
                        image = dict(type="image", asset=image_asset(rid), alt=alt)
                        if floating:
                            image["floating"] = True
                        if crop:
                            image["crop_ooxml"] = crop
                            warnings.append(f"{block_id}: Picture is cropped in Word; match its visible bounds before publishing.")
                        parts.append(image)
                    except ValueError as exc:
                        note(str(exc))
                    return
                if tag in {"object", "footnoteReference", "endnoteReference", "oMath", "oMathPara"}:
                    note(f"Inspect the rendered {tag} in the document.")
                for child in compatible_children(el):
                    visit(child, alt, floating, crop)

            visit(node)
            style_node = next((n for p in node if local(p.tag) == "pPr" for n in p if local(n.tag) == "pStyle"), None)
            style_id = attr(style_node, "val") if style_node is not None else ""
            block = dict(id=block_id, style=styles.get(style_id, style_id),
                         text="".join(p["text"] for p in parts if p["type"] == "text"), parts=parts)
            if table_path:
                block["table_path"] = table_path
            blocks.append(block)

        def walk(el, table_path=(), table_id=0, row=0, column=0):
            nonlocal table_count
            tag = local(el.tag)
            if tag == "p":
                read_paragraph(el, table_path)
                return
            if tag in {"del", "moveFrom", "sectPr"}:
                return
            if tag == "altChunk":
                warnings.append(f"After paragraph {len(blocks)}: embedded non-Word content requires a page preview.")
            if tag == "tbl":
                table_count += 1
                table_id = table_count
            if tag == "tc":
                table_path = (*table_path, dict(table=table_id, row=row, cell=column))
            r, c = 0, 0
            for child in compatible_children(el):
                name = local(child.tag)
                r += int(name == "tr")
                c += int(name == "tc")
                walk(child, table_path, table_id, r if name == "tr" else row, c if name == "tc" else column)

        walk(body)
    return dict(source=source.name, scope="Main body in XML reading order. Floating pictures follow their paragraph anchor.",
                blocks=blocks, assets=assets, warnings=warnings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    output = args.out_dir
    output.mkdir(parents=True, exist_ok=True)
    try:
        media = output / "media"
        if media.is_symlink() or (output / "manifest.json").is_symlink():
            raise ValueError("Choose an output folder without symlinked manifest or media paths.")
        with tempfile.TemporaryDirectory(dir=output) as directory:
            stage = Path(directory)
            (stage / "media").mkdir()
            manifest = extract(args.docx, stage)
            target = stage / "manifest.json"
            target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            media.mkdir(exist_ok=True)
            for file in (stage / "media").iterdir():
                file.replace(media / file.name)
            target.replace(output / "manifest.json")
        print(f"{len(manifest['blocks'])} body paragraphs, {len(manifest['assets'])} images, {len(manifest['warnings'])} warnings: {output / 'manifest.json'}")
    except (ValueError, BadZipFile, ET.ParseError, OSError, KeyError) as exc:
        parser.exit(1, f"Cannot extract DOCX: {exc}\n")


if __name__ == "__main__":
    main()
