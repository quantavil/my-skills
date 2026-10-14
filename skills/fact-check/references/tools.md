# Tools

Use existing tools; do not build a separate application or install models during a routine fact-check. Use a dedicated output directory per source; rerun the same command to reuse completed work. Run only one acquisition process per output directory. Resolve the helper path from the skill directory, not the current working directory.

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

Before audio fallback, inspect the actual system rather than assuming this machine's setup:

1. Check OS/architecture, available RAM, required commands, and the chosen runtime's `--version` and `--list-devices`. On Linux use `uname -sm` and `free -h`; on other systems use their equivalents. `nvidia-smi` can show NVIDIA free VRAM, but its absence does not mean there is no GPU: the runtime may expose Metal or Vulkan devices.
2. Resolve an existing runtime and both readable, nonempty model files. Prefer user-configured paths or an existing installation; the shared model folder below is a default, not a requirement. Do not redownload a model already available elsewhere. A binary existing on disk is insufficient if it fails to run or lacks ASR support.
3. Use GPU offload only with a working supported device and sufficient free memory. The earlier 6.4 GB observation is a guide for this configuration, not a universal threshold. With no suitable GPU, a compatible CPU build can run with `--device none -ngl 0 --no-mmproj-offload`, subject to available RAM. Explain that CPU transcription is slower; do not claim the entire fact-check is impossible solely because there is no GPU. Avoid downloading a CPU runtime without setup authorization.
4. If local transcription cannot run, use a user-configured STT service where permitted, or ask for a transcript. Explain the specific blocker (missing model, incompatible runtime/driver, insufficient memory, or unavailable service), which route is blocked, and the smallest remedy. Do not upload audio to a new external service without user authorization.

Reuse a supplied local audio file instead of downloading it. For a video URL, check these prerequisites before fetching audio. Report platform/authentication errors explicitly rather than treating a failed subtitle request as proof that subtitles do not exist.

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

Use the current session's model and available search/page-reading tools. In Codex, use its native web search and page-opening tools; in Claude Code, use `WebSearch` and `WebFetch`; in ChatGPT, use its available search capability. Read relevant sources, prefer primary evidence, and consider contradictory evidence. Tool availability depends on the host.

The transcript stays in the current session: no separate ChatGPT API call, model SDK, Tavily key, or sending it to another chat is needed. Check search availability early. If unavailable, still obtain the transcript through the normal subtitles/audio route when possible and return the transcript embedded in the fact-check request described in [report and handoff](report.md). State that verification has not been performed; do not present model memory as sourced verification. If acquisition also fails, explain that separate blocker without inventing a transcript.

Documentation: [yt-dlp](https://github.com/yt-dlp/yt-dlp), [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR), [llama.cpp](https://github.com/ggml-org/llama.cpp).
