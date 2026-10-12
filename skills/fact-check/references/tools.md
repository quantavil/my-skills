# Tools

Use existing tools; do not build a separate application or install models during skill setup. Work in a new local directory for each video. Substitute the actual URL, paths and subtitle language in the examples, passing them as quoted arguments.

## Choosing a recent channel video

When asked for a channel's latest or a recent video, list its official videos and verify the selected video's upload date and URL:

```bash
yt-dlp --flat-playlist --playlist-end 8 --print '%(id)s\t%(upload_date)s\t%(title)s' 'CHANNEL_VIDEOS_URL'
yt-dlp --no-playlist --skip-download --print '%(id)s\t%(upload_date)s\t%(duration_string)s\t%(title)s\t%(webpage_url)s' 'VIDEO_URL'
```

## Subtitles: yt-dlp

For supported video URLs, inspect available subtitle tracks:

```bash
yt-dlp --no-playlist --list-subs 'VIDEO_URL'
```

Select a track matching the spoken language; prefer human subtitles, then automatic captions:

```bash
yt-dlp --no-playlist --skip-download --write-subs --write-auto-subs --sub-langs 'LANGUAGE_CODE' --sub-format vtt -o 'source.%(ext)s' 'VIDEO_URL'
```

Read each VTT/SRT cue through the next timestamp line; YouTube VTT may put caption text after blank lines or include inline word-timing tags. Strip tags, keep cue timestamps, remove repeated rolling-caption overlap, and spot-check the opening and ending speech. A supplied readable transcript skips downloading. Empty/malformed captions trigger audio transcription.

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
print(f"Detected language: {info.language} ({info.language_probability:.2f})")
```

Check the detected language and spot-check the transcript against the audio at the beginning, middle, and end. Auto-detection can confuse Hindi and Urdu; if the speech is clearly Hindi, retry with `language="hi"`. A forced language is not proof of accuracy: if text is still garbled, use a larger multilingual model or an already-configured speech-to-text service. Do not fact-check claims from an unreliable transcript; if speech cannot be recovered, say so and mark affected claims unverifiable.

A first transcription may download the selected model; disclose this. Check prerequisites before running. If tooling is missing, report what is needed rather than fabricating a transcript. Follow the user's environment/install rules; use prebuilt dependencies and keep any temporary setup isolated.

Compatibility note: if decoding fails with `TypeError: open() got an unexpected keyword argument 'metadata_errors'`, the installed `faster-whisper` and PyAV versions are incompatible. In the tested `faster-whisper` 1.2.1 + PyAV 19 combination, use `av<19` in an isolated environment or a `faster-whisper` build containing the upstream fix. See the [upstream issue](https://github.com/SYSTRAN/faster-whisper/issues/1589).

## Fact-check: host-native tools

Use the current session's model and available search/page-reading tools. In Codex, use its native web search and page-opening tools; in Claude Code, use `WebSearch` and `WebFetch`; in ChatGPT, use its available search capability. Read relevant sources, prefer primary evidence, and consider contradictory evidence. Tool availability depends on the host.

The transcript stays in the current session: no separate ChatGPT API call, model SDK, Tavily key, or sending it to another chat is needed. If search is unavailable, disclose the limitation; do not present model memory as sourced verification.

Documentation: [yt-dlp](https://github.com/yt-dlp/yt-dlp), [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
