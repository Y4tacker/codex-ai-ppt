#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


VALID_ASPECTS = {"16:9", "4:3", "1:1"}
VALID_LANGUAGES = {"auto", "zh", "en", "ja"}
VALID_MODES = {"spark", "outline", "brief"}
VALID_STYLE_SOURCES = {"template_image", "style_description"}
VALID_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
STAGES = {
    "contract": "CONTRACT.md",
    "outline": "OUTLINE.md",
    "descriptions": "DESCRIPTIONS.md",
    "image-plan": "IMAGE_PLAN.md",
}
STATUS_AFTER_STAGE = {
    "contract": "contract_confirmed",
    "outline": "outline_confirmed",
    "descriptions": "descriptions_confirmed",
    "image-plan": "image_plan_confirmed",
}
PAGE_STATUS_ORDER = [
    "planned",
    "description_ready",
    "prompt_ready",
    "queued",
    "image_generated",
    "exported",
]
STATE_FILE = "STATE.json"
BUNDLED_NODE_ROOT = Path("/Users/hola/.cache/codex-runtimes/codex-primary-runtime/dependencies/node")


class CliError(Exception):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def ensure_run_dirs(run: Path) -> None:
    for rel in [
        "references",
        "prompts",
        "slides",
        "versions",
        "exports",
        "reports",
    ]:
        (run / rel).mkdir(parents=True, exist_ok=True)


def load_state(run: Path) -> dict:
    path = run / STATE_FILE
    if not path.exists():
        raise CliError(f"missing {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_state(run: Path, state: dict) -> None:
    state["updated_at"] = utc_now()
    path = run / STATE_FILE
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def event(run: Path, kind: str, data: dict | None = None) -> None:
    record = {"ts": utc_now(), "kind": kind, "data": data or {}}
    with (run / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def copy_template_image(run: Path, image_path: str | None) -> str | None:
    if not image_path:
        return None
    source = Path(image_path).expanduser()
    if not source.exists() or not source.is_file():
        raise CliError(f"template image not found: {source}")
    if source.suffix.lower() not in VALID_IMAGE_EXTS:
        raise CliError("template image must be PNG, JPG, JPEG, or WebP")
    dest = run / "references" / f"template{source.suffix.lower()}"
    shutil.copy2(source, dest)
    return dest.relative_to(run).as_posix()


def initial_contract(state: dict) -> str:
    style = state.get("style_source", {})
    lines = [
        "---",
        f'title: "{state.get("title", "")}"',
        f"mode: {state.get('mode')}",
        f"aspect: {state.get('aspect')}",
        f"language: {state.get('language')}",
        "style_source:",
        f"  type: {style.get('type') or ''}",
    ]
    if style.get("type") == "template_image":
        lines.append(f"  template_image: {style.get('template_image') or ''}")
    elif style.get("type") == "style_description":
        lines.append(f'  style_description: "{style.get("style_description") or ""}"')
    lines.extend(["---", "", "# Project Contract", "", "Confirm or replace this contract before downstream artifacts are treated as final.", ""])
    return "\n".join(lines)


def cmd_init(args: argparse.Namespace) -> int:
    run = Path(args.run).expanduser().resolve()
    if args.mode not in VALID_MODES:
        raise CliError(f"invalid mode: {args.mode}")
    if args.aspect not in VALID_ASPECTS:
        raise CliError(f"invalid aspect: {args.aspect}")
    if args.language not in VALID_LANGUAGES:
        raise CliError(f"invalid language: {args.language}")
    if args.style_source and args.style_source not in VALID_STYLE_SOURCES:
        raise CliError(f"invalid style source: {args.style_source}")

    run.mkdir(parents=True, exist_ok=True)
    ensure_run_dirs(run)
    template_rel = copy_template_image(run, args.template_image)
    style_source = {"type": args.style_source}
    if args.style_source == "template_image":
        style_source["template_image"] = template_rel
    elif args.style_source == "style_description":
        style_source["style_description"] = args.style_description or ""

    state = {
        "run_dir": str(run),
        "mode": args.mode,
        "title": args.title,
        "aspect": args.aspect,
        "language": args.language,
        "page_count": args.page_count,
        "status": "draft",
        "style_source": style_source,
        "artifacts": {},
        "pages": [],
        "active_versions": {},
        "versions": {},
        "stale": [],
        "orphaned_pages": [],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    save_state(run, state)
    (run / "CONTRACT.md").write_text(initial_contract(state), encoding="utf-8")
    for rel in ["OUTLINE.md", "DESCRIPTIONS.md", "IMAGE_PLAN.md", "GOAL.md"]:
        path = run / rel
        if not path.exists():
            path.write_text("", encoding="utf-8")
    event(run, "init", {"mode": args.mode, "title": args.title})
    print(str(run))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    run = Path(args.run).expanduser().resolve()
    state = load_state(run)
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"{state.get('status')} {state.get('title')}")
    return 0


def parse_pages(text: str) -> list[dict]:
    pages: list[dict] = []
    current: dict | None = None
    body: list[str] = []
    page_re = re.compile(r"^\s*(?:#{1,4}\s*)?(?:slide_id\s*[:：]\s*)?(page-\d{3,})\b", re.I)
    numbered_re = re.compile(r"^\s*(?:#{1,4}\s*)?(?:page|slide|第)\s*(\d{1,3})(?:页|[.:：\s-])\s*(.*)$", re.I)
    heading_re = re.compile(r"^\s*#{1,3}\s+(.+?)\s*$")

    def flush() -> None:
        nonlocal current, body
        if current is not None:
            current["body"] = "\n".join(body).strip()
            pages.append(current)
        current = None
        body = []

    for raw in text.splitlines():
        line = raw.rstrip()
        match = page_re.match(line)
        if match:
            flush()
            slide_id = match.group(1).lower()
            title = line[match.end() :].strip(" -:：") or slide_id
            current = {"slide_id": slide_id, "title": title}
            continue
        match = numbered_re.match(line)
        if match:
            flush()
            slide_id = f"page-{int(match.group(1)):03d}"
            title = match.group(2).strip() or slide_id
            current = {"slide_id": slide_id, "title": title}
            continue
        match = heading_re.match(line)
        if match and current is None:
            flush()
            slide_id = f"page-{len(pages) + 1:03d}"
            current = {"slide_id": slide_id, "title": match.group(1).strip()}
            continue
        if current is not None:
            body.append(line)

    flush()
    return pages


def merge_pages(existing: list[dict], parsed: list[dict]) -> list[dict]:
    by_id = {p.get("slide_id"): p for p in existing if p.get("slide_id")}
    merged: list[dict] = []
    used_ids: set[str] = set()
    next_num = 1
    for idx, page in enumerate(parsed):
        slide_id = page.get("slide_id")
        previous = by_id.get(slide_id) if slide_id else None
        if slide_id is None and previous is None and idx < len(existing):
            previous = existing[idx]
            slide_id = previous.get("slide_id")
        if not slide_id:
            while f"page-{next_num:03d}" in used_ids or f"page-{next_num:03d}" in by_id:
                next_num += 1
            slide_id = f"page-{next_num:03d}"
        used_ids.add(slide_id)
        merged_page = {
            **(previous or {}),
            "slide_id": slide_id,
            "title": page.get("title") or (previous or {}).get("title") or slide_id,
            "status": (previous or {}).get("status", "planned"),
        }
        if page.get("body"):
            merged_page["body_hash"] = sha256_text(page["body"])
        merged.append(merged_page)
    return merged


def cmd_write_artifact(args: argparse.Namespace) -> int:
    run = Path(args.run).expanduser().resolve()
    state = load_state(run)
    text = sys.stdin.read()
    filename = STAGES[args.stage]
    (run / filename).write_text(text, encoding="utf-8")
    state.setdefault("artifacts", {})[args.stage] = {
        "path": filename,
        "sha256": sha256_text(text),
        "updated_at": utc_now(),
    }
    if args.stage in {"outline", "descriptions", "image-plan"}:
        parsed = parse_pages(text)
        if parsed:
            state["pages"] = merge_pages(state.get("pages", []), parsed)
            if args.stage == "descriptions":
                for page in state["pages"]:
                    page["status"] = "description_ready"
            if args.stage == "image-plan":
                for page in state["pages"]:
                    page["status"] = "prompt_ready"
    state["status"] = STATUS_AFTER_STAGE[args.stage]
    save_state(run, state)
    event(run, "write_artifact", {"stage": args.stage, "bytes": len(text.encode("utf-8"))})
    return 0


def validate_style_source(run: Path, state: dict) -> list[str]:
    errors: list[str] = []
    style = state.get("style_source") or {}
    style_type = style.get("type")
    if style_type not in VALID_STYLE_SOURCES:
        errors.append("style_source.type must be template_image or style_description")
        return errors
    if style_type == "template_image":
        rel = style.get("template_image")
        if not rel:
            errors.append("style_source.template_image is required")
        else:
            image = run / rel
            if not image.exists() or not image.is_file():
                errors.append(f"template image is missing: {rel}")
            if image.suffix.lower() not in VALID_IMAGE_EXTS:
                errors.append("template image must be PNG, JPG, JPEG, or WebP")
    if style_type == "style_description":
        if not str(style.get("style_description") or "").strip():
            errors.append("style_source.style_description is required")
    return errors


def pages_from_state_or_artifact(run: Path, state: dict) -> list[dict]:
    pages = state.get("pages") or []
    if pages:
        return pages
    for filename in ["DESCRIPTIONS.md", "OUTLINE.md", "IMAGE_PLAN.md"]:
        path = run / filename
        if path.exists():
            parsed = parse_pages(path.read_text(encoding="utf-8"))
            if parsed:
                return parsed
    return []


def validate_stage(run: Path, stage: str, state: dict) -> list[str]:
    errors: list[str] = []
    if stage == "contract":
        if not (run / "CONTRACT.md").read_text(encoding="utf-8").strip():
            errors.append("CONTRACT.md is empty")
        errors.extend(validate_style_source(run, state))
    elif stage == "outline":
        text = (run / "OUTLINE.md").read_text(encoding="utf-8") if (run / "OUTLINE.md").exists() else ""
        if not text.strip():
            errors.append("OUTLINE.md is empty")
        if not parse_pages(text):
            errors.append("OUTLINE.md has no parseable pages")
    elif stage == "descriptions":
        text = (run / "DESCRIPTIONS.md").read_text(encoding="utf-8") if (run / "DESCRIPTIONS.md").exists() else ""
        pages = parse_pages(text)
        if not text.strip():
            errors.append("DESCRIPTIONS.md is empty")
        if not pages:
            errors.append("DESCRIPTIONS.md has no parseable pages")
        for page in pages:
            if not page.get("body"):
                errors.append(f"{page['slide_id']} has an empty description")
    elif stage == "image-plan":
        text = (run / "IMAGE_PLAN.md").read_text(encoding="utf-8") if (run / "IMAGE_PLAN.md").exists() else ""
        if not text.strip():
            errors.append("IMAGE_PLAN.md is empty")
        for page in pages_from_state_or_artifact(run, state):
            prompt = run / "prompts" / f"{page['slide_id']}.md"
            if not prompt.exists() or not prompt.read_text(encoding="utf-8").strip():
                errors.append(f"missing prompt for {page['slide_id']}")
    elif stage == "images":
        for page in pages_from_state_or_artifact(run, state):
            image = run / "slides" / f"{page['slide_id']}.png"
            if not image.exists() or image.stat().st_size == 0:
                errors.append(f"missing active slide image for {page['slide_id']}")
    elif stage == "export":
        out = run / "exports" / "deck.pptx"
        if not out.exists() or out.stat().st_size == 0:
            errors.append("exports/deck.pptx is missing")
        elif not zipfile.is_zipfile(out):
            errors.append("exports/deck.pptx is not a valid zip package")
    else:
        raise CliError(f"unknown validation stage: {stage}")
    return errors


def cmd_validate(args: argparse.Namespace) -> int:
    run = Path(args.run).expanduser().resolve()
    state = load_state(run)
    errors = validate_stage(run, args.stage, state)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        event(run, "validate_failed", {"stage": args.stage, "errors": errors})
        return 1
    print(f"{args.stage}: ok")
    return 0


def cmd_validate_style_source(args: argparse.Namespace) -> int:
    run = Path(args.run).expanduser().resolve()
    state = load_state(run)
    errors = validate_style_source(run, state)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        event(run, "validate_style_source_failed", {"errors": errors})
        return 1
    state["status"] = max_status(state.get("status"), "style_source_confirmed")
    save_state(run, state)
    print("style-source: ok")
    return 0


def max_status(current: str | None, candidate: str) -> str:
    order = [
        "draft",
        "style_source_confirmed",
        "contract_confirmed",
        "outline_confirmed",
        "descriptions_confirmed",
        "image_plan_confirmed",
        "ready_for_goal",
        "generating_images",
        "exported",
        "completed",
        "failed",
    ]
    if current not in order:
        return candidate
    if candidate not in order:
        return current
    return order[max(order.index(current), order.index(candidate))]


def cmd_smart_merge_outline(args: argparse.Namespace) -> int:
    run = Path(args.run).expanduser().resolve()
    state = load_state(run)
    text = sys.stdin.read()
    parsed = parse_pages(text)
    old_pages = state.get("pages", [])
    old_ids = {p.get("slide_id") for p in old_pages}
    state["pages"] = merge_pages(old_pages, parsed)
    new_ids = {p.get("slide_id") for p in state["pages"]}
    state["orphaned_pages"] = sorted([pid for pid in old_ids - new_ids if pid])
    state["stale"] = sorted(set(state.get("stale", [])) | {"descriptions", "image-plan", "images", "export"})
    state["status"] = "outline_confirmed"
    (run / "OUTLINE.md").write_text(text, encoding="utf-8")
    save_state(run, state)
    event(run, "smart_merge_outline", {"pages": len(state["pages"]), "orphaned": state["orphaned_pages"]})
    return 0


def next_version_id(page_dir: Path) -> str:
    page_dir.mkdir(parents=True, exist_ok=True)
    nums = []
    for path in page_dir.glob("v*.png"):
        match = re.match(r"v(\d{3})\.png$", path.name)
        if match:
            nums.append(int(match.group(1)))
    return f"v{(max(nums) + 1) if nums else 1:03d}"


def cmd_version_add(args: argparse.Namespace) -> int:
    run = Path(args.run).expanduser().resolve()
    state = load_state(run)
    image = Path(args.image).expanduser().resolve()
    prompt = Path(args.prompt).expanduser().resolve()
    if not image.exists() or image.suffix.lower() != ".png":
        raise CliError("version-add requires an existing PNG image")
    if not prompt.exists():
        raise CliError("version-add requires an existing prompt file")
    page_dir = run / "versions" / args.page
    version_id = next_version_id(page_dir)
    version_image = page_dir / f"{version_id}.png"
    shutil.copy2(image, version_image)
    prompt_dest = run / "prompts" / f"{args.page}.md"
    shutil.copy2(prompt, prompt_dest)
    slide_dest = run / "slides" / f"{args.page}.png"
    shutil.copy2(version_image, slide_dest)

    state.setdefault("versions", {}).setdefault(args.page, []).append(
        {
            "version_id": version_id,
            "image": version_image.relative_to(run).as_posix(),
            "prompt": prompt_dest.relative_to(run).as_posix(),
            "created_at": utc_now(),
        }
    )
    state.setdefault("active_versions", {})[args.page] = version_id
    seen = False
    for page in state.get("pages", []):
        if page.get("slide_id") == args.page:
            page["status"] = "image_generated"
            seen = True
    if not seen:
        state.setdefault("pages", []).append({"slide_id": args.page, "title": args.page, "status": "image_generated"})
    state["status"] = max_status(state.get("status"), "generating_images")
    save_state(run, state)
    event(run, "version_add", {"page": args.page, "version": version_id})
    print(version_id)
    return 0


def cmd_version_activate(args: argparse.Namespace) -> int:
    run = Path(args.run).expanduser().resolve()
    state = load_state(run)
    version = run / "versions" / args.page / f"{args.version}.png"
    if not version.exists():
        raise CliError(f"version does not exist: {args.page}/{args.version}")
    shutil.copy2(version, run / "slides" / f"{args.page}.png")
    state.setdefault("active_versions", {})[args.page] = args.version
    save_state(run, state)
    event(run, "version_activate", {"page": args.page, "version": args.version})
    return 0


def ppt_size(aspect: str) -> tuple[int, int]:
    if aspect == "4:3":
        return 9144000, 6858000
    if aspect == "1:1":
        return 6858000, 6858000
    return 12192000, 6858000


def write_pptx(run: Path, out: Path, state: dict) -> None:
    pages = pages_from_state_or_artifact(run, state)
    if not pages:
        raise CliError("no pages to export")
    images = []
    for page in pages:
        image = run / "slides" / f"{page['slide_id']}.png"
        if not image.exists():
            raise CliError(f"missing slide image: {image}")
        images.append((page["slide_id"], image))

    cx, cy = ppt_size(state.get("aspect", "16:9"))
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types(len(images)))
        z.writestr("_rels/.rels", root_rels())
        z.writestr("docProps/core.xml", core_xml(state.get("title") or "Codex AI PPT Deck"))
        z.writestr("docProps/app.xml", app_xml(len(images)))
        z.writestr("ppt/presentation.xml", presentation_xml(len(images), cx, cy))
        z.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(images)))
        z.writestr("ppt/theme/theme1.xml", theme_xml())
        z.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels())
        z.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels())
        for idx, (_, image) in enumerate(images, start=1):
            z.write(image, f"ppt/media/image{idx}.png")
            z.writestr(f"ppt/slides/slide{idx}.xml", slide_xml(idx, cx, cy))
            z.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", slide_rels(idx))


def artifact_export_spec(run: Path, out: Path, state: dict) -> dict:
    pages = pages_from_state_or_artifact(run, state)
    spec_pages = []
    for page in pages:
        image = run / "slides" / f"{page['slide_id']}.png"
        if not image.exists():
            raise CliError(f"missing slide image: {image}")
        spec_pages.append(
            {
                "slide_id": page["slide_id"],
                "title": page.get("title") or page["slide_id"],
                "image": str(image),
            }
        )
    if not spec_pages:
        raise CliError("no pages to export")
    return {
        "title": state.get("title") or "Codex AI PPT Deck",
        "aspect": state.get("aspect", "16:9"),
        "out": str(out),
        "pages": spec_pages,
    }


def node_executable() -> str:
    candidates = [
        os.environ.get("CODEX_AI_PPT_NODE"),
        str(BUNDLED_NODE_ROOT / "bin" / "node"),
        shutil.which("node"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return "node"


def node_cwd() -> Path | None:
    if BUNDLED_NODE_ROOT.exists():
        return BUNDLED_NODE_ROOT
    return None


def try_export_pptx_artifact_tool(run: Path, out: Path, state: dict) -> tuple[bool, str | None]:
    script = Path(__file__).resolve().parent / "export_pptx_artifact.mjs"
    if not script.exists():
        return False, "artifact-tool exporter script is missing"
    spec = artifact_export_spec(run, out, state)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False)
        spec_path = Path(f.name)
    try:
        result = subprocess.run(
            [node_executable(), str(script), str(spec_path)],
            cwd=str(node_cwd()) if node_cwd() else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    finally:
        try:
            spec_path.unlink()
        except OSError:
            pass
    if result.returncode != 0:
        reason = (result.stderr or result.stdout or "artifact-tool export failed").strip()
        return False, reason[-1000:]
    if not out.exists() or out.stat().st_size == 0:
        return False, "artifact-tool export did not create a PPTX"
    return True, None


def content_types(slide_count: int) -> str:
    slide_overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  {slide_overrides}
</Types>'''


def root_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''


def core_xml(title: str) -> str:
    now = utc_now()
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escape(title)}</dc:title>
  <dc:creator>Codex AI PPT</dc:creator>
  <cp:lastModifiedBy>Codex AI PPT</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>'''


def app_xml(slide_count: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex AI PPT</Application>
  <PresentationFormat>On-screen Show</PresentationFormat>
  <Slides>{slide_count}</Slides>
</Properties>'''


def presentation_xml(slide_count: int, cx: int, cy: int) -> str:
    slides = "\n".join(f'<p:sldId id="{255 + i}" r:id="rId{i}"/>' for i in range(1, slide_count + 1))
    master_rid = slide_count + 1
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId{master_rid}"/></p:sldMasterIdLst>
  <p:sldIdLst>{slides}</p:sldIdLst>
  <p:sldSz cx="{cx}" cy="{cy}" type="screen16x9"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>'''


def presentation_rels(slide_count: int) -> str:
    rels = [
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, slide_count + 1)
    ]
    rels.append(
        f'<Relationship Id="rId{slide_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    )
    rels.append(
        f'<Relationship Id="rId{slide_count + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>'
    )
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  ' + "\n  ".join(rels) + "\n</Relationships>"


def slide_xml(idx: int, cx: int, cy: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/><a:chOff x="0" y="0"/><a:chExt cx="{cx}" cy="{cy}"/></a:xfrm></p:grpSpPr>
      <p:pic>
        <p:nvPicPr><p:cNvPr id="{idx + 1}" name="page-{idx:03d}.png"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
        <p:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
        <p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
      </p:pic>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>'''


def slide_rels(idx: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image{idx}.png"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>'''


def theme_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Codex AI PPT">
  <a:themeElements>
    <a:clrScheme name="Codex AI PPT"><a:dk1><a:srgbClr val="000000"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="1F2937"/></a:dk2><a:lt2><a:srgbClr val="F9FAFB"/></a:lt2><a:accent1><a:srgbClr val="2563EB"/></a:accent1><a:accent2><a:srgbClr val="10B981"/></a:accent2><a:accent3><a:srgbClr val="F59E0B"/></a:accent3><a:accent4><a:srgbClr val="EF4444"/></a:accent4><a:accent5><a:srgbClr val="8B5CF6"/></a:accent5><a:accent6><a:srgbClr val="06B6D4"/></a:accent6><a:hlink><a:srgbClr val="2563EB"/></a:hlink><a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink></a:clrScheme>
    <a:fontScheme name="Codex AI PPT"><a:majorFont><a:latin typeface="Arial"/></a:majorFont><a:minorFont><a:latin typeface="Arial"/></a:minorFont></a:fontScheme>
    <a:fmtScheme name="Codex AI PPT"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
  </a:themeElements>
</a:theme>'''


def slide_master_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>'''


def slide_master_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>'''


def slide_layout_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>'''


def slide_layout_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>'''


def cmd_export_pptx(args: argparse.Namespace) -> int:
    run = Path(args.run).expanduser().resolve()
    state = load_state(run)
    out = Path(args.out).expanduser().resolve() if args.out else run / "exports" / "deck.pptx"
    out.parent.mkdir(parents=True, exist_ok=True)
    artifact_ok, artifact_reason = try_export_pptx_artifact_tool(run, out, state)
    if artifact_ok:
        event(run, "export_pptx_artifact_tool", {"out": str(out)})
    else:
        event(run, "export_pptx_fallback", {"reason": artifact_reason or "unknown", "out": str(out)})
        write_pptx(run, out, state)
    if out.resolve() != (run / "exports" / "deck.pptx").resolve():
        (run / "exports").mkdir(exist_ok=True)
        shutil.copy2(out, run / "exports" / "deck.pptx")
    for page in state.get("pages", []):
        if page.get("status") == "image_generated":
            page["status"] = "exported"
    state["status"] = "exported"
    save_state(run, state)
    event(run, "export_pptx", {"out": str(out)})
    print(str(out))
    return 0


def cmd_final_status(args: argparse.Namespace) -> int:
    run = Path(args.run).expanduser().resolve()
    state = load_state(run)
    checks = {
        "style_source": validate_style_source(run, state),
        "descriptions": validate_stage(run, "descriptions", state),
        "image_plan": validate_stage(run, "image-plan", state),
        "images": validate_stage(run, "images", state),
        "export": validate_stage(run, "export", state),
    }
    errors = [err for errs in checks.values() for err in errs]
    ready = not errors
    if ready:
        state["status"] = "completed"
        save_state(run, state)
        report = run / "reports" / "final.md"
        report.write_text(f"# Final Status\n\nready: true\ncompleted_at: {utc_now()}\n", encoding="utf-8")
    payload = {
        "ready": ready,
        "status": state.get("status"),
        "errors": errors,
        "checks": {name: not errs for name, errs in checks.items()},
        "pptx": "exports/deck.pptx",
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("ready=true" if ready else "ready=false")
        for err in errors:
            print(f"ERROR: {err}")
    return 0 if ready else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-ai-ppt")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--run", required=True)
    init.add_argument("--mode", required=True, choices=sorted(VALID_MODES))
    init.add_argument("--title", required=True)
    init.add_argument("--aspect", default="16:9", choices=sorted(VALID_ASPECTS))
    init.add_argument("--language", default="auto", choices=sorted(VALID_LANGUAGES))
    init.add_argument("--style-source", choices=sorted(VALID_STYLE_SOURCES))
    init.add_argument("--template-image")
    init.add_argument("--style-description")
    init.add_argument("--page-count")
    init.set_defaults(func=cmd_init)

    status = sub.add_parser("status")
    status.add_argument("--run", required=True)
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    write = sub.add_parser("write-artifact")
    write.add_argument("--run", required=True)
    write.add_argument("--stage", required=True, choices=sorted(STAGES))
    write.add_argument("--stdin", action="store_true")
    write.set_defaults(func=cmd_write_artifact)

    validate = sub.add_parser("validate")
    validate.add_argument("--run", required=True)
    validate.add_argument("--stage", required=True, choices=["contract", "outline", "descriptions", "image-plan", "images", "export"])
    validate.set_defaults(func=cmd_validate)

    vss = sub.add_parser("validate-style-source")
    vss.add_argument("--run", required=True)
    vss.set_defaults(func=cmd_validate_style_source)

    merge = sub.add_parser("smart-merge-outline")
    merge.add_argument("--run", required=True)
    merge.add_argument("--stdin", action="store_true")
    merge.set_defaults(func=cmd_smart_merge_outline)

    add = sub.add_parser("version-add")
    add.add_argument("--run", required=True)
    add.add_argument("--page", required=True)
    add.add_argument("--image", required=True)
    add.add_argument("--prompt", required=True)
    add.set_defaults(func=cmd_version_add)

    activate = sub.add_parser("version-activate")
    activate.add_argument("--run", required=True)
    activate.add_argument("--page", required=True)
    activate.add_argument("--version", required=True)
    activate.set_defaults(func=cmd_version_activate)

    export = sub.add_parser("export-pptx")
    export.add_argument("--run", required=True)
    export.add_argument("--out")
    export.set_defaults(func=cmd_export_pptx)

    final = sub.add_parser("final-status")
    final.add_argument("--run", required=True)
    final.add_argument("--json", action="store_true")
    final.set_defaults(func=cmd_final_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
