# Output Contract

Each job writes one self-contained directory:

| File | Purpose |
|---|---|
| `source.json` | Input kind, source identifier, model, requested language, and WAV normalization settings. Never contains cookie contents or cookie paths. |
| `audio.wav` | Mono 16 kHz PCM WAV used for transcription. |
| `transcript.txt` | Plain transcript text in chronological order. |
| `transcript.srt` | Numbered subtitle segments with millisecond timestamps. |
| `transcript.json` | Detected language, probability, duration, and timestamped segments. |
| `report.md` | Human-readable completion summary and warnings. |

The standard WAV format is PCM signed 16-bit little-endian, 16,000 Hz, one channel. Preserve the source file; temporary URL downloads may be removed after `audio.wav` is verified.

If transcription fails after WAV creation, retain `audio.wav` for retry and do not present empty transcript files as a successful result.
