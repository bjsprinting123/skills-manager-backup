from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


HEADING = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def heading_sections(text: str) -> list[dict]:
    matches = list(HEADING.finditer(text))
    if not matches:
        return []
    sections = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(
            {
                "title": match.group(2).strip(),
                "level": len(match.group(1)),
                "start_char": start,
                "end_char": end,
                "chars": end - start,
            }
        )
    return sections


def window_sections(text: str, max_chars: int) -> list[dict]:
    paragraphs = [(m.start(), m.end()) for m in re.finditer(r"(?s).*?(?:\n\s*\n|\Z)", text) if m.group(0).strip()]
    if not paragraphs:
        return [{"title": "part-001", "level": 0, "start_char": 0, "end_char": len(text), "chars": len(text)}]
    out = []
    start = paragraphs[0][0]
    last = start
    part = 1
    for pstart, pend in paragraphs:
        if pend - start > max_chars and last > start:
            out.append({"title": f"part-{part:03d}", "level": 0, "start_char": start, "end_char": last, "chars": last - start})
            part += 1
            start = pstart
        last = pend
    if last > start:
        out.append({"title": f"part-{part:03d}", "level": 0, "start_char": start, "end_char": last, "chars": last - start})
    return out


def build_index(path: Path, max_chars: int) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    sections = heading_sections(text)
    mode = "headings"
    if not sections:
        sections = window_sections(text, max_chars)
        mode = "paragraph-windows"
    for i, section in enumerate(sections, 1):
        section["id"] = f"S{i:04d}"
        snippet = text[section["start_char"]:section["end_char"]].strip().replace("\n", " ")
        section["preview"] = snippet[:160]
    return {
        "schema_version": 1,
        "source": str(path),
        "sha256": sha256(path),
        "encoding": "utf-8-sig",
        "characters": len(text),
        "index_mode": mode,
        "sections": sections,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Deterministic long-source indexer")
    p.add_argument("source")
    p.add_argument("--out")
    p.add_argument("--max-chars", type=int, default=12000)
    args = p.parse_args()
    source = Path(args.source).resolve()
    if not source.is_file():
        raise SystemExit(f"source missing: {source}")
    result = build_index(source, args.max_chars)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(encoded, encoding="utf-8")
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
