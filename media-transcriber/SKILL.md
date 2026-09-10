---
name: media-transcriber
description: Download audio-only media from supported URLs or transcribe local audio and video with Faster-Whisper, producing a normalized WAV plus TXT, SRT, JSON, and a run report. Use for media download, speech-to-text, subtitle generation, or WAV extraction; do not use for content summarization or ComfyUI workflow analysis.
---

# Media Transcriber

Turn one URL or local media file into a reproducible transcript bundle while avoiding unnecessary full-video downloads.

## Runtime

Use the managed runtime at `E:\tools\media-transcriber`:

- Python: `E:\tools\media-transcriber\venv\Scripts\python.exe`
- FFmpeg: `E:\tools\media-transcriber\bin`
- FFprobe: optional; Windows application control may block it, and this skill does not require it
- yt-dlp: `E:\tools\media-transcriber\bin\yt-dlp.exe`
- default model: `E:\tools\media-transcriber\models\small`

The executable entry point is `scripts/media_transcriber.py` in this skill folder. Run its `check` command before the first job or after runtime changes.

## Workflow

1. Determine whether the input is a URL or a local audio/video file.
2. For a URL, download only the best available audio stream by default. Do not download the full video unless the user explicitly asks for it.
3. Normalize the input to mono 16 kHz PCM WAV with FFmpeg.
4. Read that PCM WAV directly and pass its sample array to Faster-Whisper. Do not load PyAV when Windows application control blocks its native extension.
5. Default to Chinese when the user has identified the language as Chinese; otherwise use automatic language detection.
6. Produce the complete output bundle described in [references/output-contract.md](references/output-contract.md).
7. Report the output directory, detected language, duration, segment count, and any fallback or warning.

Use this command shape:

```powershell
& 'E:\tools\media-transcriber\venv\Scripts\python.exe' '<skill-dir>\scripts\media_transcriber.py' transcribe --input '<URL-or-file>' --output-dir '<output-dir>' --language zh
```

For authenticated sites, add `--cookies '<cookies.txt>'`. Add `--proxy '<proxy-url>'` only when the user has provided or approved that proxy. Never print, copy into the skill, or include cookie contents in output files. A cookies path is permitted in the command but must not be written to the manifest or report.

Existing output files are protected by default. Use `--overwrite` only when the user requested replacement or the target directory was created for the current run.

## Operating Boundaries

- Do not delete source media after transcription unless the user explicitly asks.
- Do not retain temporary URL downloads after successful conversion; the script handles its own temporary directory.
- Do not summarize or reinterpret the transcript unless separately requested.
- Do not treat platform subtitles as verified speech. If platform subtitles are used in a future workflow, label their source and preserve them separately from Whisper output.
- Stop and report the exact missing component when environment checks fail. Do not silently install packages, download models, or mutate credentials during an ordinary transcription request.

## Validation

Run:

```powershell
& 'E:\tools\media-transcriber\venv\Scripts\python.exe' '<skill-dir>\scripts\media_transcriber.py' check
```

Success requires the Faster-Whisper inference core, FFmpeg, yt-dlp, and the configured Whisper model. PyAV and FFprobe are reported separately as optional and must not be bypassed when Windows application control blocks them.
