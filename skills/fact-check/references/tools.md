# Tools

Use a dedicated output directory per source and one acquisition process per directory. Rerun the same command to resume. Resolve helper paths from the skill directory. Routine checks reuse installed tools/models; setup is a separate task.

## Prerequisites and installation

A supplied transcript needs only the host AI session and its search tools. Fetching video subtitles needs `yt-dlp`. Audio fallback additionally needs `ffmpeg`, `curl`, Python 3, a Qwen3-ASR-capable llama.cpp build, and both GGUF files below. No Tavily key or separate AI API key is required for host-native fact-checking.

On Ubuntu/Debian, install the basic tools when setting up a new machine:

```bash
sudo apt-get update
sudo apt-get install yt-dlp ffmpeg curl python3
```

If a website stops working with the distribution's yt-dlp version, update it using the [official installation instructions](https://github.com/yt-dlp/yt-dlp#installation).

For local audio transcription:

- Get a compatible build from [llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases), or build it following the project's instructions. The build must support Qwen3-ASR and the `/v1/audio/transcriptions` endpoint. Use a CUDA build with a compatible NVIDIA driver to run on the GPU.
- Download `Qwen3-ASR-1.7B-Q8_0.gguf` and `mmproj-Qwen3-ASR-1.7B-Q8_0.gguf` from the [official GGUF model repository](https://huggingface.co/ggml-org/Qwen3-ASR-1.7B-GGUF/tree/main). Both files are required; together they occupy about 2.52 GB on disk.
- On this machine, the model folder is `~/.local/share/models/Qwen3-ASR-1.7B-GGUF-Q8_0/`. The runtime and bundled CUDA libraries are in `~/.local/share/fact-check/runtime/`; `factcheck-llama-server` launches the installed build with those libraries. This launcher is local setup, not a command supplied by llama.cpp. On another machine, adapt the launcher/path to its installation.
- The installed configuration used about 6.4 GB of GPU memory in short English and Hindi tests. Longer recordings may need chunking. Python Qwen, PyTorch, faster-whisper, and Voicebox are not prerequisites for this GGUF workflow.

Check only prerequisites for the selected route: subtitles and supplied transcripts do not require a GPU or ASR model. Installations are setup work; routine fact-checking uses the existing installation.

Before audio fallback, run the helper's `doctor` command. Inspect OS/architecture, RAM (on Linux), commands, runtime version/devices, and both readable model files. Prefer user-configured paths or existing installations; do not redownload a model already elsewhere. Runtime startup establishes compatibility and memory fit, not a file merely existing. Missing NVIDIA tools do not rule out Metal/Vulkan devices. If a route is blocked, name the specific problem and smallest remedy. A supplied transcript or usable subtitles bypass ASR entirely. Reuse supplied audio rather than downloading it; external STT uploads require existing authorization.

## Choosing a recent channel video

When asked for a channel's latest or a recent video, list its official videos and verify the selected video's upload date and URL:

```bash
yt-dlp --flat-playlist --playlist-end 8 --print '%(id)s\t%(upload_date)s\t%(title)s' 'CHANNEL_VIDEOS_URL'
yt-dlp --no-playlist --skip-download --print '%(id)s\t%(upload_date)s\t%(duration_string)s\t%(title)s\t%(webpage_url)s' 'VIDEO_URL'
```

## Transcript helper

The helper uses Python 3’s standard library and the installed tools above. It never installs models, calls an AI/search API, or translates. Run it from any directory using its actual path:

```bash
python3 /path/to/fact-check/scripts/transcript.py doctor
python3 /path/to/fact-check/scripts/transcript.py fetch 'VIDEO_URL' --output '/path/to/job'
python3 /path/to/fact-check/scripts/transcript.py fetch '/path/to/recording.mp3' --output '/path/to/job'
```

`fetch` also accepts supplied `.txt`, `.vtt`, or `.srt` files. Supplied text/captions bypass ASR prerequisites. For URLs, it inspects subtitle tracks and prefers human captions in the spoken language, then automatic captions, then audio. If the language is unknown and multiple tracks exist, specify `--language hi` (or the actual code). Do not select translated captions as a substitute for the original speech. Platform/authentication errors stop acquisition; they are not treated as absent subtitles.

`doctor` reports commands, model locations, available RAM on Linux, and runtime version/devices. Exit code 2 means local audio prerequisites are incomplete; supplied text or subtitle acquisition may still work. It is a preliminary check: model compatibility and memory fit are established when the server actually starts.

Set `ASR_SERVER` to an executable path and `ASR_MODEL_DIR` to an existing shared model folder to override defaults. The helper prefers this machine’s installed launcher before a generic `llama-server`. `--device auto` uses a device exposed by the runtime, otherwise CPU; `--device cpu` explicitly disables GPU offload. On insufficient GPU memory, inspect `asr-server.log` and retry with CPU if RAM permits. Do not assume no GPU prevents transcription. No automatic downloads or external STT uploads occur.

Audio is converted to 16 kHz mono WAV and processed in sequential 60-second chunks, with a one-second overlap on each side to preserve boundary speech, using one temporary localhost server. Only matching repeated boundary words are removed (ignoring case and punctuation) from the combined transcript; raw responses remain available. `--chunk-seconds 30` changes the chunk size; use a new output directory when changing source, language, chunk size or model. The server is stopped on success, failure, or interruption. Each successful raw ASR response is cached, and rerunning an interrupted/partial job reuses it. `--audio-only` explicitly skips URL subtitles for an audio-fallback test.

Outputs:

- `transcript.txt`: original-language text, with rolling-caption overlap and Qwen’s language metadata prefix removed.
- `segments.json`: subtitle cues or audio chunk ranges; chunk ranges are not word timestamps.
- `metadata.json`: source details, acquisition method, language, status, coverage and failed chunk ranges. `complete` means the acquisition finished; it does not certify transcription accuracy or complete subtitle coverage.
- Original captions or downloaded audio, raw ASR responses, and server logs remain in the job directory for inspection. Models remain in their shared location.

Exit codes: 0 = acquisition complete/reused, 2 = partial transcript, 1 = failure, 130 = interrupted. Always inspect metadata before using a transcript. Failed chunks are listed as gaps; never describe a partial result as the complete recording. A supplied subtitle track may omit speech even when parsing succeeds.

Check names, numbers, negations, and the opening/middle/ending speech against the audio when audio playback is available. Inspect adjacent chunks where boundary speech or overlap deduplication is ambiguous. Report unreviewed ASR when you cannot listen; do not claim to have heard or checked audio merely because the model processed it. Do not silently repair uncertain words from context or invent timestamps. Preserve the raw transcript; flag uncertainty or add a clearly marked correction after checking the audio. If the transcript is garbled or the detected language is wrong, use usable subtitles, an already-authorized STT service, or explain the blocker.

## Fact-check: host-native tools

Use the current session's model and available search/page-reading tools. In Codex, use its native web search and page-opening tools; in Claude Code, use `WebSearch` and `WebFetch`; in ChatGPT, use its available search capability. Tool availability depends on the host.

No separate ChatGPT API call, SDK or Tavily key is needed. Check search availability early; if unavailable, still acquire the transcript when possible, then follow the complete-transcript handoff in [report](report.md).
Documentation: [yt-dlp](https://github.com/yt-dlp/yt-dlp), [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR), [llama.cpp](https://github.com/ggml-org/llama.cpp).
