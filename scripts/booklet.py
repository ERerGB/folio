#!/usr/bin/env python3
"""Build and track EPUB booklet editions; optionally deliver via local BOOXDrop."""

from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid4, uuid5
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo


STYLE = """html{background:#fff;color:#111}body{max-width:42em;margin:0 auto;padding:1.2em 1.2em 4em;font-family:serif;font-size:1.05em;line-height:1.8}h1,h2,h3{line-height:1.35}h1{font-size:1.6em}h2{font-size:1.25em}h3{font-size:1.1em}p{margin:1em 0}blockquote{border-left:.16em solid #555;margin:1.3em 0;padding:0 0 0 1em}li{margin:.35em 0}a{color:inherit}.subtitle,.note{color:#444}.chapter{break-before:page}"""
DELIVERY_STAGES = ("uploaded", "device-file", "library-indexed", "opened")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dump_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def initial_state() -> dict:
    return {"schema_version": 1, "archived": False, "pending": None, "releases": [], "deliveries": []}


def load_state(root: Path) -> dict:
    path = root / "lifecycle.json"
    state = read_json(path) if path.exists() else initial_state()
    if state.get("schema_version") != 1:
        raise ValueError("Unsupported lifecycle schema")
    return state


def load_book(root: Path) -> tuple[dict, list[dict]]:
    book = read_json(root / "book.json")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", book.get("id", "")):
        raise ValueError("book.id must use lowercase letters, digits and hyphens")
    if not book.get("title") or not book.get("chapters"):
        raise ValueError("book.json needs a title and at least one chapter")
    chapters = []
    seen = set()
    for item in book["chapters"]:
        chapter_id = item.get("id", "")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", chapter_id) or chapter_id in seen:
            raise ValueError("Chapter IDs must be unique, lowercase slugs")
        seen.add(chapter_id)
        path = (root / item["file"]).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f"Chapter file missing or outside object: {item['file']}")
        chapter = {"id": chapter_id, "title": item["title"], "text": path.read_text(encoding="utf-8")}
        if "source_refs" in item:
            refs = item["source_refs"]
            if not isinstance(refs, list) or any(
                not isinstance(ref, dict) or not all(isinstance(ref.get(key), str) and ref[key].strip()
                                                     for key in ("kind", "id")) for ref in refs
            ):
                raise ValueError(f"Chapter {chapter_id} needs source_refs with kind and id")
            chapter["source_refs"] = refs
        if "revision_note" in item:
            if not isinstance(item["revision_note"], str):
                raise ValueError(f"Chapter {chapter_id} revision_note must be text")
            chapter["revision_note"] = item["revision_note"]
        chapters.append(chapter)
    return book, chapters


def content_hash(book: dict, chapters: list[dict]) -> str:
    content = {"id": book["id"], "title": book["title"], "filename_stem": book.get("filename_stem", book["id"]), "subtitle": book.get("subtitle", ""),
               "language": book.get("language", "en"), "description": book.get("description", ""),
               "chapters": chapters}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def source_snapshot(book: dict, chapters: list[dict], edition: int, created_at: str) -> dict:
    return {"book_id": book["id"], "edition": edition, "created_at": created_at,
            "chapters": [{"id": ch["id"], "title": ch["title"],
                          "content_sha256": hashlib.sha256(ch["text"].encode("utf-8")).hexdigest(),
                          "source_refs": ch.get("source_refs", []),
                          "revision_note": ch.get("revision_note", "")}
                         for ch in chapters]}


def inline(text: str) -> str:
    value = html.escape(text, quote=True)
    value = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                   lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    return re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", value)


def render_markdown(source: str) -> str:
    blocks: list[str] = []
    pending: list[str] = []
    mode = "paragraph"

    def flush() -> None:
        nonlocal pending
        if not pending:
            return
        if mode == "paragraph":
            blocks.append("<p>" + inline(" ".join(pending)) + "</p>")
        elif mode == "quote":
            blocks.append("<blockquote><p>" + inline(" ".join(pending)) + "</p></blockquote>")
        elif mode in ("ul", "ol"):
            blocks.append(f"<{mode}>" + "".join(f"<li>{inline(x)}</li>" for x in pending) + f"</{mode}>")
        pending = []

    for raw in source.splitlines() + [""]:
        line = raw.strip()
        if not line:
            flush()
            mode = "paragraph"
            continue
        heading = re.match(r"^(#{2,3})\s+(.+)$", line)
        if heading:
            flush()
            tag = "h2" if len(heading.group(1)) == 2 else "h3"
            blocks.append(f"<{tag}>{inline(heading.group(2))}</{tag}>")
            mode = "paragraph"
            continue
        if line.startswith("> "):
            new_mode, value = "quote", line[2:]
        elif re.match(r"^[-*] \S", line):
            new_mode, value = "ul", line[2:]
        elif re.match(r"^\d+\. \S", line):
            new_mode, value = "ol", re.sub(r"^\d+\. ", "", line)
        else:
            new_mode, value = "paragraph", line
        if mode != new_mode:
            flush()
            mode = new_mode
        pending.append(value)
    return "\n".join(blocks)


def xhtml(title: str, body: str, lang: str) -> str:
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>'
            f'<html xmlns="http://www.w3.org/1999/xhtml" lang="{html.escape(lang)}" xml:lang="{html.escape(lang)}">'
            f'<head><title>{html.escape(title)}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>'
            f'<body>{body}</body></html>')


def zip_write(zf: ZipFile, name: str, text: str, compression: int = ZIP_DEFLATED) -> None:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = compression
    zf.writestr(info, text.encode("utf-8"))


def render(book: dict, chapters: list[dict], edition: int, created_at: str, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem_base = re.sub(r'[\\/:*?"<>|]+', "-", book.get("filename_stem", book["id"])).strip(" .")
    if not stem_base or len(stem_base) > 80:
        raise ValueError("filename_stem must be 1–80 safe characters")
    stem = f"{stem_base}-e{edition:03d}"
    epub_path, html_path = out_dir / f"{stem}.epub", out_dir / f"{stem}.html"
    lang = book.get("language", "en")
    labels = {"edition": "第 {number} 版", "download": "下载 EPUB", "contents": "目录"} if lang.lower().startswith("zh") else {"edition": "Edition {number}", "download": "Download EPUB", "contents": "Contents"}
    title = book["title"]
    subtitle = book.get("subtitle", "")
    description = book.get("description", "")
    rendered = [render_markdown(ch["text"]) for ch in chapters]
    toc = "".join(f'<li><a href="#chapter-{html.escape(ch["id"])}">{html.escape(ch["title"])}</a></li>' for ch in chapters)
    sections = "".join(f'<section class="chapter" id="chapter-{html.escape(ch["id"])}"><h2>{html.escape(ch["title"])}</h2>{body}</section>' for ch, body in zip(chapters, rendered))
    html_page = (f'<!doctype html><html lang="{html.escape(lang)}"><head><meta charset="utf-8">'
                 f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>'
                 f'<style>{STYLE}</style></head><body><main><h1>{html.escape(title)}</h1>'
                 f'<p class="subtitle">{html.escape(subtitle)} · {labels["edition"].format(number=edition)}</p>'
                 f'<p class="note">{html.escape(description)}</p><p><a href="{epub_path.name}">{labels["download"]}</a></p>'
                 f'<nav><h2>{labels["contents"]}</h2><ol>{toc}</ol></nav>{sections}</main></body></html>')
    html_path.write_text(html_page, encoding="utf-8")

    nav_items = "".join(f'<li><a href="chapter-{i}.xhtml">{html.escape(ch["title"])}</a></li>' for i, ch in enumerate(chapters, 1))
    nav = (f'<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE html>'
           f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"'
           f' lang="{html.escape(lang)}" xml:lang="{html.escape(lang)}"><head><title>{labels["contents"]}</title>'
           f'<link rel="stylesheet" type="text/css" href="style.css"/></head><body><h1>{html.escape(title)}</h1>'
           f'<nav epub:type="toc" id="toc"><h2>{labels["contents"]}</h2><ol>{nav_items}</ol></nav></body></html>')
    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="style" href="style.css" media-type="text/css"/>']
    spine = []
    for i in range(1, len(chapters) + 1):
        manifest.append(f'<item id="c{i}" href="chapter-{i}.xhtml" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="c{i}"/>')
    opf = (f'<?xml version="1.0" encoding="UTF-8"?>'
           f'<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="{html.escape(lang)}">'
           f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bookid">urn:uuid:{uuid5(NAMESPACE_URL, "ebook:" + book["id"])}</dc:identifier>'
           f'<dc:title>{html.escape(title)}</dc:title><dc:language>{html.escape(lang)}</dc:language>'
           f'<dc:description>{html.escape(description)}</dc:description><meta property="dcterms:modified">{created_at}</meta>'
           f'</metadata><manifest>{"".join(manifest)}</manifest><spine>{"".join(spine)}</spine></package>')
    container = ('<?xml version="1.0" encoding="UTF-8"?><container version="1.0" '
                 'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                 '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                 '</rootfiles></container>')
    with ZipFile(epub_path, "w") as zf:
        zip_write(zf, "mimetype", "application/epub+zip", ZIP_STORED)
        zip_write(zf, "META-INF/container.xml", container)
        zip_write(zf, "OEBPS/content.opf", opf)
        zip_write(zf, "OEBPS/nav.xhtml", nav)
        zip_write(zf, "OEBPS/style.css", STYLE)
        for i, (ch, body) in enumerate(zip(chapters, rendered), 1):
            zip_write(zf, f"OEBPS/chapter-{i}.xhtml", xhtml(ch["title"], f'<h1>{html.escape(ch["title"])}</h1>{body}', lang))
    with ZipFile(epub_path) as zf:
        assert zf.namelist()[0] == "mimetype" and zf.read("mimetype") == b"application/epub+zip"
        for name in zf.namelist():
            if name.endswith((".xml", ".opf", ".xhtml")):
                ElementTree.fromstring(zf.read(name))
    return epub_path, html_path


def artifact_path(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Edition file is outside booklet object")
    return path


def select_candidate(root: Path, state: dict) -> dict:
    candidate = state.get("pending") or (state["releases"][-1] if state["releases"] else None)
    if candidate is None:
        raise ValueError("Build an edition before delivery")
    path = artifact_path(root, candidate["epub_path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != candidate["epub_sha256"]:
        raise ValueError("Built EPUB missing or changed; rebuild before delivery")
    if "sources_path" in candidate:
        sources = artifact_path(root, candidate["sources_path"])
        if not sources.is_file() or hashlib.sha256(sources.read_bytes()).hexdigest() != candidate["sources_sha256"]:
            raise ValueError("Edition source snapshot missing or changed; restore it or revise the edition")
    return candidate


def record_delivery(root: Path, state: dict, candidate: dict, device: str, transport: str,
                    remote_path: str, verified_size: int, evidence: str,
                    endpoint: str | None = None, stage: str = "uploaded") -> dict:
    if not all(value.strip() for value in (device, transport, remote_path, evidence)):
        raise ValueError("Delivery device, transport, path and evidence must be non-empty")
    if stage not in DELIVERY_STAGES:
        raise ValueError(f"Delivery stage must be one of: {', '.join(DELIVERY_STAGES)}")
    if verified_size != candidate["epub_size"]:
        raise ValueError("Verified remote size differs from the built EPUB")
    existing = [x for x in state["deliveries"] if x["edition"] == candidate["edition"] and x["device"] == device]
    if existing:
        delivery = existing[-1]
        if (delivery["transport"] != transport or delivery["remote_path"] != remote_path
                or delivery["epub_sha256"] != candidate["epub_sha256"]):
            raise ValueError("Existing delivery identity differs; inspect the destination before updating")
        previous_stage = delivery.get("stage")
        if previous_stage in DELIVERY_STAGES and DELIVERY_STAGES.index(stage) < DELIVERY_STAGES.index(previous_stage):
            raise ValueError("Delivery stage cannot move backward")
        if previous_stage == stage:
            return delivery
        history = delivery.setdefault("stage_history", [])
        if previous_stage is None:
            history.append({"stage": "legacy-verified", "verified_at": delivery["verified_at"],
                            "evidence": delivery["verification_evidence"]})
        event = {"stage": stage, "verified_at": now(), "evidence": evidence}
        history.append(event)
        delivery.update({"stage": stage, "verified_at": event["verified_at"], "verification_evidence": evidence})
        dump_json(root / "lifecycle.json", state)
        return delivery
    if state.get("pending") and state["pending"]["edition"] == candidate["edition"]:
        state["releases"].append(state["pending"])
        state["pending"] = None
    verified_at = now()
    delivery = {"edition": candidate["edition"], "device": device, "transport": transport,
                "remote_path": remote_path, "verified_size": verified_size,
                "epub_sha256": candidate["epub_sha256"], "verified_at": verified_at,
                "verification_evidence": evidence, "stage": stage,
                "stage_history": [{"stage": stage, "verified_at": verified_at, "evidence": evidence}]}
    if endpoint:
        delivery["endpoint"] = endpoint
    state["deliveries"].append(delivery)
    dump_json(root / "lifecycle.json", state)
    return delivery


def get_json(url: str) -> dict:
    with urlopen(url, timeout=8) as response:
        return json.load(response)


def device_url(host: str) -> str:
    match = re.fullmatch(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})", host)
    private_lans = [ipaddress.ip_network(x) for x in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
    if not match or not 1 <= int(match.group(2)) <= 65535 or not any(
        ipaddress.ip_address(match.group(1)) in network for network in private_lans
    ):
        raise ValueError("--host must be an RFC 1918 LAN IPv4 address with port")
    return "http://" + host


def current_digest(root: Path) -> str:
    return content_hash(*load_book(root))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "build", "status", "send-booxdrop", "record-delivery", "archive", "resume"):
        sub = commands.add_parser(name)
        sub.add_argument("book_dir", type=Path)
        if name == "init":
            sub.add_argument("--id", required=True)
            sub.add_argument("--title", required=True)
            sub.add_argument("--subtitle", default="")
            sub.add_argument("--language", default="en")
        elif name == "build":
            sub.add_argument("--export-dir", type=Path)
        elif name == "send-booxdrop":
            sub.add_argument("--host", required=True)
            sub.add_argument("--device", required=True)
        elif name == "record-delivery":
            sub.add_argument("--device", required=True)
            sub.add_argument("--transport", required=True)
            sub.add_argument("--remote-path", required=True)
            sub.add_argument("--verified-size", type=int, required=True)
            sub.add_argument("--evidence", required=True)
            sub.add_argument("--stage", choices=DELIVERY_STAGES, default="uploaded")
            sub.add_argument("--endpoint")
    args = parser.parse_args()
    root = args.book_dir.resolve()

    if args.command == "init":
        if root.exists() and any(root.iterdir()):
            raise ValueError("Object directory is not empty")
        root.mkdir(parents=True, exist_ok=True)
        (root / "chapters").mkdir(exist_ok=True)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.id):
            raise ValueError("--id must use lowercase letters, digits and hyphens")
        dump_json(root / "book.json", {"id": args.id, "title": args.title, "filename_stem": args.id, "subtitle": args.subtitle,
                                      "language": args.language, "description": "", "source_refs": [], "chapters": []})
        dump_json(root / "lifecycle.json", initial_state())
        print(json.dumps({"created": str(root)}, ensure_ascii=False))
        return

    state = load_state(root)
    if args.command == "status":
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return
    if args.command in ("archive", "resume"):
        state["archived"] = args.command == "archive"
        dump_json(root / "lifecycle.json", state)
        print(json.dumps({"archived": state["archived"]}))
        return

    if args.command == "build":
        if state["archived"]:
            raise ValueError("Object is archived; resume before building")
        book, chapters = load_book(root)
        digest = content_hash(book, chapters)
        last = state["releases"][-1] if state["releases"] else None
        if last and last["content_sha256"] == digest:
            if state.get("pending"):
                state["pending"] = None
                dump_json(root / "lifecycle.json", state)
            candidate = last
            result = "unchanged"
        else:
            previous = state.get("pending")
            edition = previous["edition"] if previous else (last["edition"] + 1 if last else 1)
            created_at = previous["created_at"] if previous else now()
            epub, html_file = render(book, chapters, edition, created_at, root / "editions")
            sources = epub.with_suffix(".sources.json")
            dump_json(sources, source_snapshot(book, chapters, edition, created_at))
            candidate = {"edition": edition, "content_sha256": digest, "created_at": created_at,
                         "epub_path": str(epub.relative_to(root)), "html_path": str(html_file.relative_to(root)),
                         "epub_sha256": hashlib.sha256(epub.read_bytes()).hexdigest(), "epub_size": epub.stat().st_size,
                         "sources_path": str(sources.relative_to(root)),
                         "sources_sha256": hashlib.sha256(sources.read_bytes()).hexdigest()}
            state["pending"] = candidate
            dump_json(root / "lifecycle.json", state)
            result = "pending"
        if args.export_dir:
            args.export_dir.mkdir(parents=True, exist_ok=True)
            for key in ("epub_path", "html_path"):
                shutil.copy2(artifact_path(root, candidate[key]), args.export_dir / Path(candidate[key]).name)
        print(json.dumps({"result": result, **candidate}, ensure_ascii=False))
        return

    candidate = select_candidate(root, state)
    if current_digest(root) != candidate["content_sha256"]:
        raise ValueError("Chapter content changed after the last build; build again first")
    if args.command == "record-delivery":
        result = record_delivery(root, state, candidate, args.device, args.transport,
                                 args.remote_path, args.verified_size, args.evidence, args.endpoint, args.stage)
        print(json.dumps(result, ensure_ascii=False))
        return

    if state["archived"]:
        raise ValueError("Object is archived; resume before sending")
    base = device_url(args.host)
    with urlopen(base + "/", timeout=8) as response:
        page = response.read(10000).decode("utf-8", "replace")
    if "BOOX Drop" not in page:
        raise ValueError("Address did not identify as a BOOXDrop page")
    device = get_json(base + "/api/device")
    if device.get("model") != args.device:
        raise ValueError(f"Device model mismatch: expected {args.device}, got {device.get('model')}")
    booklist = get_json(base + "/api/library").get("visibleBookList", [])
    filename = Path(candidate["epub_path"]).name
    matches = [b for b in booklist if b.get("name") == filename]
    logged = [d for d in state["deliveries"] if d["edition"] == candidate["edition"] and d["device"] == args.device]
    if logged:
        if matches:
            matched = next((b for b in matches if b.get("metadata", {}).get("size") == candidate["epub_size"]), None)
            remote_path = (matched or {}).get("metadata", {}).get("location") or (matched or {}).get("metadata", {}).get("nativeAbsolutePath")
            if not remote_path:
                raise ValueError("Matching BOOXDrop file size or path could not be verified")
            if logged[-1]["remote_path"] != remote_path:
                raise ValueError("BOOXDrop path differs from the recorded delivery; inspect before retrying")
            if logged[-1].get("stage") not in DELIVERY_STAGES[1:]:
                delivery = record_delivery(root, state, candidate, args.device, "booxdrop-local", remote_path,
                                           candidate["epub_size"], "BOOXDrop listed matching filename, size and path",
                                           base, "device-file")
                print(json.dumps({"result": "stage-updated", "delivery": delivery}, ensure_ascii=False))
                return
            print(json.dumps({"result": "already-delivered", "delivery": logged[-1]}, ensure_ascii=False))
            return
        raise ValueError("Delivery ledger says this edition was sent, but it is not visible in the root library list; inspect before retrying")
    if matches:
        raise ValueError("Same-named remote file exists without this delivery record; inspect before retrying")

    file_bytes = artifact_path(root, candidate["epub_path"]).read_bytes()
    if len(file_bytes) > 50_000_000:
        raise ValueError("Local BOOXDrop helper limits EPUBs to 50 MB")
    boundary = "codex-" + uuid4().hex
    parts = []
    for key, value in (("parent", "null"), ("sender", "Codex")):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                  'Content-Type: application/epub+zip\r\n\r\n').encode("utf-8"))
    parts.extend((file_bytes, f"\r\n--{boundary}--\r\n".encode()))
    request = Request(base + "/api/library/upload", data=b"".join(parts), method="POST",
                      headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urlopen(request, timeout=30) as response:
        uploaded = json.load(response)
    if uploaded.get("code") != 0 or not uploaded.get("successful"):
        raise ValueError(f"BOOXDrop did not confirm upload: {uploaded}")
    matches = [b for b in get_json(base + "/api/library").get("visibleBookList", []) if b.get("name") == filename]
    match = next((b for b in matches if b.get("metadata", {}).get("size") == candidate["epub_size"]), None)
    if not match:
        raise ValueError("Upload returned success but Library did not show the expected name and size; delivery not recorded")
    remote_path = match.get("metadata", {}).get("location") or match.get("metadata", {}).get("nativeAbsolutePath")
    if not remote_path:
        raise ValueError("Library omitted the remote path; delivery not recorded")
    delivery = record_delivery(root, state, candidate, args.device, "booxdrop-local", remote_path,
                               candidate["epub_size"], "BOOXDrop listed matching filename, size and path", base,
                               "device-file")
    print(json.dumps({"result": "delivered", "delivery": delivery}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"booklet: {exc}", file=sys.stderr)
        sys.exit(1)
