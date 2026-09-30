from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


def find_ffprobe(explicit: str | None) -> str:
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return str(p)
        raise SystemExit(f"ffprobe missing: {p}")
    found = shutil.which("ffprobe")
    if found:
        return found
    common = Path(r"E:\tools\media-transcriber\bin\ffprobe.exe")
    if common.is_file():
        return str(common)
    raise SystemExit("ffprobe not found; pass --ffprobe")


def main() -> int:
    p = argparse.ArgumentParser(description="Read real media metadata without modifying media")
    p.add_argument("media")
    p.add_argument("--ffprobe")
    args = p.parse_args()
    media = Path(args.media).resolve()
    if not media.is_file():
        raise SystemExit(f"media missing: {media}")
    ffprobe = find_ffprobe(args.ffprobe)
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        str(media),
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")
    raw = json.loads(proc.stdout)
    streams = []
    for s in raw.get("streams", []):
        streams.append(
            {
                "index": s.get("index"),
                "codec_type": s.get("codec_type"),
                "codec_name": s.get("codec_name"),
                "width": s.get("width"),
                "height": s.get("height"),
                "r_frame_rate": s.get("r_frame_rate"),
                "sample_rate": s.get("sample_rate"),
                "channels": s.get("channels"),
                "duration": s.get("duration"),
            }
        )
    fmt = raw.get("format", {})
    result = {
        "status": "READABLE",
        "path": str(media),
        "bytes": media.stat().st_size,
        "duration": fmt.get("duration"),
        "format_name": fmt.get("format_name"),
        "streams": streams,
    }
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
