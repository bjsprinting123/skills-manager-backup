---
name: tavily-search
description: Run targeted Tavily web searches through the local CLI when current web research or source discovery is required; archive raw JSON when the project requests reproducible evidence.
---

# Tavily Search

Use the local wrapper `E:\tools\tavily\tvly.cmd` for searches. It invokes the configured Tavily CLI with the project Python runtime.

## Workflow

1. Form a focused query and prefer authoritative domains when researching technical or product facts.
2. Run `E:\tools\tavily\tvly.cmd search "<query>" --json`. For reproducible work, prefer `--json -o "<archive-file>.json"` so the complete response is preserved without printing it.
3. Treat search as discovery. Use `tvly extract <direct-url> --format markdown --json -o "<archive-file>.json"` when the source page itself is needed for verification.
4. For project work that requires traceability, write the complete JSON response to the project's designated archive directory (for the ComfyUI documentation project: `D:\Zcode Spaces\机智罗工作流文档\查证存档\`). Use a descriptive filename and never expose credentials.
5. Separate source-backed facts from estimates or inferences in the resulting document; include direct source links near claims.

## Safety and failures

- Never print, store, or commit a Tavily API key. If authentication is missing, report that the CLI needs configuration instead of embedding a key.
- Do not treat search snippets as verified facts when the source page can be opened.
- On this Windows host, the wrapper loads `tavily_cli` from `C:\Users\ZLY\AppData\Roaming\uv\tools\tavily-cli\Lib\site-packages`. A restricted Codex sandbox may deny that path and produce `ModuleNotFoundError: No module named 'tavily_cli'` even when the package and API configuration are valid. In that exact case, verify the package path read-only and rerun the same wrapper with the narrow `require_escalated` permission; do not reinstall, relogin, or switch providers merely because of this sandbox-only error.
- The wrapper is a Windows batch file that forwards `%*`. Do not pass a URL containing a raw `&` query separator because `cmd.exe` can reparse it as a command boundary. Prefer an equivalent URL with one query parameter, percent-encode the query safely, or call the underlying Python entry point with an argument array.
- If another wrapper or CLI failure occurs, capture the non-sensitive error, check that the paths exist, and report the blocker without modifying protected source directories.
