#!/usr/bin/env python3
"""Download or read media, normalize it to WAV, and transcribe it."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import wave
from datetime import datetime, timezone
from urllib.parse import urlparse


DEFAULT_HOME = Path(os.environ.get("MEDIA_TRANSCRIBER_HOME", r"E:\tools\media-transcriber"))
DEFAULT_MODEL = DEFAULT_HOME / "models" / "small"
LEGACY_MODEL = Path(r"E:\tools\whisper_models\small")
LEGACY_YTDLP = Path(r"E:\tools\yt-dlp.exe")


def executable(name: str, legacy: Path | None = None) -> Path | None:
    suffix = ".exe" if os.name == "nt" else ""
    managed = DEFAULT_HOME / "bin" / f"{name}{suffix}"
    if managed.is_file():
        return managed
    found = shutil.which(name)
    if found:
        return Path(found)
    if legacy and legacy.is_file():
        return legacy
    return None


def model_path(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    if DEFAULT_MODEL.is_dir():
        return DEFAULT_MODEL
    return LEGACY_MODEL


def command_status(path: Path | None, version_flag: str = "-version") -> dict[str, object]:
    if not path:
        return {"ok": False, "path": None, "version": "missing"}
    try:
        result = subprocess.run(
            [str(path), version_flag], capture_output=True, text=True, timeout=20
        )
        text = (result.stdout or result.stderr).splitlines()
        return {
            "ok": result.returncode == 0,
            "path": str(path),
            "version": text[0].strip() if text else f"exit {result.returncode}",
        }
    except Exception as exc:
        return {"ok": False, "path": str(path), "version": f"error: {exc}"}


def whisper_model_class():
    if "av" not in sys.modules:
        sys.modules["av"] = types.ModuleType("av")
    from faster_whisper import WhisperModel

    return WhisperModel


def whisper_core_status() -> dict[str, object]:
    try:
        whisper_model_class()
        import ctranslate2

        return {"ok": True, "ctranslate2": ctranslate2.__version__, "decoder": "external_ffmpeg"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "decoder": "external_ffmpeg"}


def check_environment(model: str | None = None) -> int:
    pyav_available = bool(importlib.util.find_spec("av"))
    checks = {
        "python": sys.executable,
        "faster_whisper": whisper_core_status(),
        "pyav_optional": {
            "installed": pyav_available,
            "used": False,
            "reason": "audio is decoded by the managed FFmpeg binary",
        },
        "ffmpeg": command_status(executable("ffmpeg")),
        "ffprobe_optional": command_status(executable("ffprobe")),
        "yt_dlp": command_status(executable("yt-dlp", LEGACY_YTDLP), "--version"),
        "model": str(model_path(model)),
        "model_exists": model_path(model).is_dir(),
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    ok = all(
        [
            checks["faster_whisper"]["ok"],
            checks["ffmpeg"]["ok"],
            checks["yt_dlp"]["ok"],
            checks["model_exists"],
        ]
    )
    return 0 if ok else 1


def is_url(value: str) -> bool:
    return urlparse(value).scheme.lower() in {"http", "https"}


def run_checked(command: list[str], label: str) -> None:
    result = subprocess.run(command, text=True)
    if result.returncode:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")


def download_audio(url: str, directory: Path, cookies: str | None, proxy: str | None) -> Path:
    ytdlp = executable("yt-dlp", LEGACY_YTDLP)
    if not ytdlp:
        raise FileNotFoundError("yt-dlp was not found")
    template = directory / "source.%(ext)s"
    command = [
        str(ytdlp),
        "--no-playlist",
        "--no-part",
        "-f",
        "bestaudio/best",
        "-o",
        str(template),
    ]
    if cookies:
        command.extend(["--cookies", str(Path(cookies).expanduser().resolve())])
    if proxy:
        command.extend(["--proxy", proxy])
    command.append(url)
    run_checked(command, "audio download")
    candidates = [
        path
        for path in directory.glob("source.*")
        if path.is_file() and path.suffix not in {".part", ".ytdl"}
    ]
    if not candidates:
        raise RuntimeError("yt-dlp completed but no downloaded audio file was found")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def normalize_wav(source: Path, destination: Path, overwrite: bool) -> None:
    ffmpeg = executable("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg was not found")
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if overwrite else "-n",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    run_checked(command, "WAV normalization")
    if not destination.is_file() or destination.stat().st_size <= 44:
        raise RuntimeError("FFmpeg did not produce a valid WAV file")


def load_pcm_wav(path: Path):
    import numpy as np

    with wave.open(str(path), "rb") as wav_file:
        properties = (
            wav_file.getnchannels(),
            wav_file.getsampwidth(),
            wav_file.getframerate(),
        )
        if properties != (1, 2, 16000):
            raise RuntimeError(
                "audio.wav is not mono 16-bit 16 kHz PCM: " + str(properties)
            )
        frames = wav_file.readframes(wav_file.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def require_empty_targets(output_dir: Path, overwrite: bool) -> None:
    targets = [
        output_dir / name
        for name in (
            "source.json",
            "audio.wav",
            "transcript.txt",
            "transcript.srt",
            "transcript.json",
            "report.md",
        )
    ]
    existing = [str(path) for path in targets if path.exists()]
    if existing and not overwrite:
        raise FileExistsError("output files already exist; use --overwrite: " + ", ".join(existing))


def transcribe(args: argparse.Namespace) -> int:
    if check_environment(args.model):
        raise RuntimeError("environment check failed")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    require_empty_targets(output_dir, args.overwrite)
    wav_path = output_dir / "audio.wav"
    input_kind = "url" if is_url(args.input) else "local_file"

    if input_kind == "local_file":
        source = Path(args.input).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"input file not found: {source}")
        normalize_wav(source, wav_path, args.overwrite)
    else:
        with tempfile.TemporaryDirectory(prefix=".download-", dir=output_dir) as temp:
            source = download_audio(args.input, Path(temp), args.cookies, args.proxy)
            normalize_wav(source, wav_path, args.overwrite)

    selected_model = model_path(args.model)
    WhisperModel = whisper_model_class()
    model = WhisperModel(
        str(selected_model),
        device=args.device,
        compute_type=args.compute_type,
        cpu_threads=args.cpu_threads,
    )
    language = None if args.language == "auto" else args.language
    audio_samples = load_pcm_wav(wav_path)
    segments_iter, info = model.transcribe(
        audio_samples,
        language=language,
        beam_size=args.beam_size,
        vad_filter=not args.no_vad,
        condition_on_previous_text=False,
    )
    segments = [
        {"id": index, "start": seg.start, "end": seg.end, "text": seg.text.strip()}
        for index, seg in enumerate(segments_iter, 1)
        if seg.text.strip()
    ]
    if not segments:
        raise RuntimeError("transcription produced no speech segments; audio.wav was retained")

    transcript_text = "".join(item["text"] for item in segments)
    srt_text = "\n".join(
        f'{item["id"]}\n{srt_time(item["start"])} --> {srt_time(item["end"])}\n{item["text"]}\n'
        for item in segments
    )
    duration = max(item["end"] for item in segments)
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_kind": input_kind,
        "source": args.input,
        "model": str(selected_model),
        "requested_language": args.language,
        "wav": {"sample_rate": 16000, "channels": 1, "codec": "pcm_s16le"},
    }
    result = {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration_seconds": duration,
        "segments": segments,
    }
    (output_dir / "source.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "transcript.txt").write_text(transcript_text, encoding="utf-8")
    (output_dir / "transcript.srt").write_text(srt_text, encoding="utf-8")
    (output_dir / "transcript.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = (
        "# Media transcription report\n\n"
        f"- Input: `{input_kind}`\n"
        f"- Detected language: `{info.language}` ({info.language_probability:.3f})\n"
        f"- Transcript duration: `{duration:.3f}` seconds\n"
        f"- Segments: `{len(segments)}`\n"
        f"- Model: `{selected_model}`\n"
        "- Audio: `audio.wav`, mono 16 kHz PCM s16le\n"
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    summary = {
        "status": "ok",
        "output_dir": str(output_dir),
        "language": info.language,
        "duration_seconds": duration,
        "segments": len(segments),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="validate the managed runtime")
    check.add_argument("--model")

    job = commands.add_parser("transcribe", help="download/read and transcribe one media input")
    job.add_argument("--input", required=True)
    job.add_argument("--output-dir", required=True)
    job.add_argument("--cookies")
    job.add_argument("--proxy")
    job.add_argument("--model")
    job.add_argument("--language", default="auto")
    job.add_argument("--device", default="cpu")
    job.add_argument("--compute-type", default="int8")
    job.add_argument("--cpu-threads", type=int, default=min(8, os.cpu_count() or 4))
    job.add_argument("--beam-size", type=int, default=5)
    job.add_argument("--no-vad", action="store_true")
    job.add_argument("--overwrite", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "check":
            return check_environment(args.model)
        return transcribe(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
