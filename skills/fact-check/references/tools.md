# Tools

Use existing tools; do not build a separate application or install models during skill setup. Work in a new local directory for each video. Substitute the actual URL, paths and subtitle language in the examples, passing them as quoted arguments.

## Subtitles: yt-dlp

For supported video URLs, inspect available subtitle tracks:

```bash
yt-dlp --no-playlist --list-subs 'VIDEO_URL'
```

Select a track matching the spoken language; prefer human subtitles, then automatic captions:

```bash
yt-dlp --no-playlist --skip-download --write-subs --write-auto-subs --sub-langs 'LANGUAGE_CODE' --sub-format vtt -o 'source.%(ext)s' 'VIDEO_URL'
```

Read the VTT/SRT cues as the transcript, keeping timestamps and removing repeated rolling-caption overlap. A supplied readable transcript skips downloading. Empty/malformed captions trigger audio transcription.

## Audio fallback: yt-dlp + faster-whisper

Download/extract audio (FFmpeg must be available):

```bash
yt-dlp --no-playlist -x --audio-format wav -o 'audio.%(ext)s' 'VIDEO_URL'
```

Use faster-whisper's transcription API, which preserves the spoken language:

```python
from pathlib import Path
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe("audio.wav", task="transcribe", vad_filter=True)
rows = [f"[{s.start:.2f}s–{s.end:.2f}s] {s.text.strip()}"
        for s in segments if s.text.strip()]
if not rows:
    raise RuntimeError("No usable speech transcript")
Path("transcript.txt").write_text("\n".join(rows), encoding="utf-8")
```

Check prerequisites before running. A first transcription may download the selected model; disclose this. Use an already-configured speech-to-text service if the user prefers it. If tooling is missing, report what is needed rather than fabricating a transcript. Follow the user's environment/install rules; use prebuilt dependencies.

## Fact-check: host-native tools

Use the current session's model and available search/page-reading tools. In Codex, use its native web search and page-opening tools; in Claude Code, use `WebSearch` and `WebFetch`; in ChatGPT, use its available search capability. Read relevant sources, prefer primary evidence, and consider contradictory evidence. Tool availability depends on the host.

The transcript stays in the current session: no separate ChatGPT API call, model SDK, Tavily key, or sending it to another chat is needed. If search is unavailable, disclose the limitation; do not present model memory as sourced verification.

Documentation: [yt-dlp](https://github.com/yt-dlp/yt-dlp), [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
