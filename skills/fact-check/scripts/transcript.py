#!/usr/bin/env python3
"""Acquire transcripts using installed yt-dlp, ffmpeg and Qwen GGUF. No AI/search API."""
import argparse
from contextlib import contextmanager
import hashlib
import html
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

MODEL = 'Qwen3-ASR-1.7B-Q8_0.gguf'
PROJECTOR = 'mmproj-Qwen3-ASR-1.7B-Q8_0.gguf'


def run(argv, timeout=120):
    result = subprocess.run([str(x) for x in argv], text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{Path(str(argv[0])).name} failed: {result.stderr[-2500:] or result.stdout[-2500:]}')
    return result.stdout


def save(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def runtime_paths():
    configured = os.environ.get('ASR_SERVER')
    default = Path.home() / '.local/share/fact-check/runtime/factcheck-llama-server'
    server = configured or (str(default) if default.is_file() else shutil.which('llama-server'))
    if server:
        server = shutil.which(server) or str(Path(server).expanduser().resolve())
    model_dir = Path(os.environ.get('ASR_MODEL_DIR', '~/.local/share/models/Qwen3-ASR-1.7B-GGUF-Q8_0')).expanduser().resolve()
    return server, model_dir


def doctor():
    server, model_dir = runtime_paths()
    report = {'system': platform.platform(), 'commands': {x: shutil.which(x) for x in ('yt-dlp', 'ffmpeg', 'ffprobe', 'curl')},
              'runtime': server, 'model_directory': str(model_dir), 'models': {}, 'errors': []}
    for name in (MODEL, PROJECTOR):
        path = model_dir / name
        report['models'][name] = path.stat().st_size if path.is_file() and os.access(path, os.R_OK) else 0
    if server:
        for flag, key in (('--version', 'runtime_version'), ('--list-devices', 'devices')):
            try:
                # Some builds print device/version information to stderr.
                result = subprocess.run([server, flag], capture_output=True, text=True, timeout=30)
                report[key] = (result.stdout + result.stderr).strip()
                if result.returncode:
                    report['errors'].append(f'Runtime {flag} exited {result.returncode}')
            except (OSError, subprocess.TimeoutExpired) as exc:
                report['errors'].append(str(exc))
    if platform.system() == 'Linux':
        try:
            report['memory'] = run(['free', '-h']).strip()
        except (OSError, RuntimeError):
            pass
    report['audio_ready'] = bool(server and all(report['models'].values()) and
                                 all(report['commands'][x] for x in ('ffmpeg', 'ffprobe', 'curl')) and not report['errors'])
    report['note'] = 'Readiness is preliminary; starting the server verifies model/endpoint compatibility. Subtitles need only yt-dlp; supplied text needs no ASR.'
    return report


def seconds(value):
    parts = value.replace(',', '.').split(':')
    total = 0.0
    for part in parts:
        total = total * 60 + float(part)
    return total


def parse_captions(content):
    """Parse SRT/VTT cues; remove rolling overlap only for overlapping cues."""
    stamp = re.compile(r'^\s*((?:\d+:)?\d{2}:\d{2}[.,]\d{3})\s+-->\s+((?:\d+:)?\d{2}:\d{2}[.,]\d{3})')
    cues = []
    current = None
    lines = []
    previous_words = []
    previous_end = -1

    def flush():
        nonlocal previous_words, previous_end
        if current is None:
            return
        text = html.unescape(re.sub(r'<[^>]*>', '', ' '.join(lines)))
        words = text.split()
        complete = words[:]
        if current[0] < previous_end:
            for count in range(min(len(previous_words), len(words)), 0, -1):
                if previous_words[-count:] == words[:count]:
                    words = words[count:]
                    break
        if words and current[1] > current[0]:
            cues.append({'start': current[0], 'end': current[1], 'text': ' '.join(words)})
        previous_words, previous_end = complete, current[1]

    source_lines = content.splitlines()
    for index, line in enumerate(source_lines):
        match = stamp.match(line)
        if match:
            flush()
            current = (seconds(match[1]), seconds(match[2]))
            lines = []
        elif current is not None and line.strip():
            following = next((item for item in source_lines[index + 1:] if item.strip()), '') if line.strip().isdigit() else ''
            if not (line.strip().isdigit() and stamp.match(following)):
                lines.append(line.strip())
    flush()
    return cues


def choose_caption(info, requested):
    manual = info.get('subtitles') or {}
    automatic = info.get('automatic_captions') or {}
    language = requested or info.get('language')
    if not language:
        languages = {x for x in manual.keys() | automatic.keys() if x != 'live_chat'}
        if len(languages) > 1:
            raise ValueError('Spoken language unknown; select --language from: ' + ', '.join(sorted(languages)))
        language = next(iter(languages), None)
    if not language:
        return None
    for kind, tracks in (('manual', manual), ('automatic', automatic)):
        candidates = [x for x in tracks if x != 'live_chat' and
                      (x == language or x.startswith(language + '-')) and tracks[x]]
        if candidates:
            return kind, min(candidates, key=lambda x: (x != language, len(x), x))
    return None


def deduplicate_segments(segments):
    """Remove repeated boundary tokens (ignoring case/punctuation) only where chunk time ranges overlap."""
    output = []
    previous = None
    def normalized(words):
        return [word.casefold().strip(".,!?;:'\"()[]{}।…“”‘’") for word in words]
    for segment in segments:
        words = segment['text'].split()
        if previous and segment['start'] < previous['end']:
            before = previous['text'].split()
            for count in range(min(len(before), len(words)), 0, -1):
                if normalized(before[-count:]) == normalized(words[:count]):
                    words = words[count:]
                    break
        if words:
            output.append({**segment, 'text': ' '.join(words)})
        previous = segment
    return output


def asr_text(result):
    if result.get('n_truncated', 0) or result.get('truncated', False):
        raise ValueError('ASR reported truncated output; retry shorter chunks in a new output directory')
    raw = result.get('text')
    if not isinstance(raw, str):
        raise ValueError('ASR returned no text string')
    match = re.match(r'^\s*language\s+([^<\r\n]+)<asr_text>', raw, re.I)
    language = match[1].strip() if match else 'unknown'
    text = (raw[match.end():] if match else raw).strip()
    if not text:
        raise ValueError('ASR returned empty speech; inspect the audio and raw response')
    return text, language


@contextmanager
def server_session(folder, check, device):
    gpu_available = bool(re.search(r'^\s*\S+\d+:', check.get('devices', ''), re.M))
    gpu = device == 'gpu' or (device == 'auto' and gpu_available)
    if device == 'gpu' and not gpu_available:
        raise RuntimeError('No supported GPU exposed by runtime; use --device cpu or fix the runtime/driver')
    if not gpu:
        print('Using CPU transcription; this may be slow.', file=sys.stderr)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    model_dir = Path(check['model_directory'])
    command = [check['runtime'], '-m', str(model_dir / MODEL), '--mmproj', str(model_dir / PROJECTOR),
               '-ngl', '99' if gpu else '0', '-c', '32768', '-np', '1', '--no-webui',
               '--host', '127.0.0.1', '--port', str(port)]
    command += ['--mmproj-offload'] if gpu else ['--device', 'none', '--no-mmproj-offload']
    with (folder / 'asr-server.log').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('ASR server exited; inspect asr-server.log. Check RAM/VRAM, model and runtime compatibility; try --device cpu if GPU memory is insufficient.')
                try:
                    with urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                time.sleep(0.5)
            else:
                raise RuntimeError('ASR startup timed out; inspect asr-server.log')
            yield f'http://127.0.0.1:{port}/v1/audio/transcriptions'
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def transcribe(audio, folder, args, check):
    wav = folder / 'audio-16k.wav'
    if not wav.exists():
        temporary = folder / 'audio-16k.tmp.wav'
        run(['ffmpeg', '-v', 'error', '-y', '-i', audio, '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', temporary], timeout=1800)
        temporary.replace(wav)
    duration = float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', wav]).strip())
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Audio has no valid duration')
    chunks = folder / 'chunks'
    chunks.mkdir(exist_ok=True)
    segments, gaps, languages = [], [], set()
    # Cache identity includes the source, model versions and chunking parameters.
    fingerprint = hashlib.sha256(json.dumps({'audio': digest(wav), 'chunk': args.chunk_seconds, 'overlap_seconds': 1,
        'models': [(str(Path(check['model_directory']) / name), (Path(check['model_directory']) / name).stat().st_mtime_ns, check['models'][name]) for name in (MODEL, PROJECTOR)],
        'runtime': check.get('runtime_version')}, sort_keys=True).encode()).hexdigest()
    cache = chunks / 'identity.json'
    if cache.exists() and json.loads(cache.read_text()) != fingerprint:
        raise ValueError('ASR settings/model changed; use a new --output directory')
    save(cache, fingerprint)
    with server_session(folder, check, args.device) as endpoint:
        for index in range(math.ceil(duration / args.chunk_seconds)):
            start = max(0, index * args.chunk_seconds - 1)
            end = min(duration, (index + 1) * args.chunk_seconds + 1)
            # Small overlap preserves boundary speech; raw responses remain available.
            chunk = chunks / f'{index:05d}.wav'
            result_path = chunks / f'{index:05d}.json'
            print(f'Transcribing {start:.1f}–{end:.1f}s', file=sys.stderr)
            try:
                if not result_path.exists():
                    run(['ffmpeg', '-v', 'error', '-y', '-ss', str(start), '-i', wav, '-t', str(end - start), chunk])
                    temporary = result_path.with_suffix('.tmp')
                    run(['curl', '--connect-timeout', '5', '--max-time', '1800', '-fsS', '-F', f'file=@{chunk}',
                         '-F', 'model=Qwen3-ASR', '-F', 'response_format=json', endpoint, '-o', temporary], timeout=1810)
                    # Invalid/empty responses are not cached as successful chunks.
                    asr_text(json.loads(temporary.read_text(encoding='utf-8')))
                    temporary.replace(result_path)
                text, language = asr_text(json.loads(result_path.read_text(encoding='utf-8')))
                languages.add(language)
                segments.append({'start': start, 'end': end, 'text': text})
            except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
                gaps.append({'start': start, 'end': end, 'error': str(exc)})
    return deduplicate_segments(segments), {'duration_seconds': duration, 'language': ', '.join(sorted(languages)), 'gaps': gaps,
                      'coverage': 'partial' if gaps else 'full audio processed; ASR accuracy unreviewed',
                      'timing': 'chunk ranges, not word timestamps', 'boundary_review': 'Chunks overlap by one second on each side; matching boundary repeats removed (case/punctuation ignored). Review ambiguous speech.', 'method': 'Qwen3-ASR-1.7B Q8_0'}


def fetch(args):
    folder = args.output.expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    local = Path(args.source).expanduser()
    is_url = args.source.startswith(('https://', 'http://'))
    if not is_url and not local.is_file():
        raise ValueError('Source must be an existing local file or an HTTP(S) video URL')
    identity = {'source': args.source if is_url else str(local.resolve()), 'source_sha256': None if is_url else digest(local),
                'language': args.language, 'audio_only': args.audio_only, 'chunk_seconds': args.chunk_seconds}
    metadata_path = folder / 'metadata.json'
    old = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {}
    if old and old.get('input') != identity:
        raise ValueError('Output directory belongs to a different source/settings; use a new --output directory')
    if not old and any(folder.iterdir()):
        raise ValueError('Output directory contains unrecognized files; choose an empty directory')
    transcript = folder / 'transcript.txt'
    if old.get('status') == 'complete' and transcript.exists() and old.get('transcript_sha256') == digest(transcript):
        print(json.dumps({'status': 'reused', 'output': str(folder)}, ensure_ascii=False))
        return 0
    metadata = {'input': identity, 'status': 'processing', 'source': identity['source'], 'audio_reviewed': False}
    save(metadata_path, metadata)
    try:
        segments = []
        audio = None
        if not is_url and local.suffix.lower() in ('.txt', '.vtt', '.srt'):
            text = local.read_text(encoding='utf-8-sig')
            if local.suffix.lower() in ('.vtt', '.srt'):
                segments = parse_captions(text)
                if not segments:
                    raise ValueError('No usable subtitle cues; supply audio or a valid transcript')
            else:
                if not text.strip():
                    raise ValueError('Supplied transcript is empty')
                segments = [{'text': text.strip()}]
            metadata.update(method='supplied captions' if local.suffix.lower() != '.txt' else 'supplied text',
                            language=args.language or 'unknown', coverage='supplied content; completeness unverified')
        elif is_url:
            info_path = folder / 'source.json'
            if info_path.exists():
                info = json.loads(info_path.read_text(encoding='utf-8'))
            else:
                info = json.loads(run(['yt-dlp', '--no-playlist', '--skip-download', '--dump-single-json', '--', args.source]))
                # Cache track choices without persisting signed media URLs or request headers.
                info = {k: info.get(k) for k in ('id', 'title', 'webpage_url', 'upload_date', 'duration', 'language', 'subtitles', 'automatic_captions')}
                for key in ('subtitles', 'automatic_captions'):
                    info[key] = {lang: [{'ext': item.get('ext')}] for lang, items in (info.get(key) or {}).items() if items for item in items[:1]}
                save(info_path, info)
            metadata.update({k: info.get(k) for k in ('id', 'title', 'webpage_url', 'upload_date', 'duration')})
            choice = None if args.audio_only else choose_caption(info, args.language)
            if choice:
                kind, lang = choice
                caption_dir = folder / 'captions'
                caption_dir.mkdir(exist_ok=True)
                existing = list(caption_dir.glob('*.vtt')) + list(caption_dir.glob('*.srt'))
                if not existing:
                    run(['yt-dlp', '--no-playlist', '--skip-download', '--write-subs' if kind == 'manual' else '--write-auto-subs',
                         '--sub-langs', '^' + re.escape(lang) + '$', '--sub-format', 'vtt/srt', '-o', str(caption_dir / 'source.%(ext)s'), '--', args.source])
                    existing = list(caption_dir.glob('*.vtt')) + list(caption_dir.glob('*.srt'))
                if existing:
                    segments = parse_captions(existing[0].read_text(encoding='utf-8-sig'))
                metadata.update(method=f'{kind} captions', language=lang, coverage='subtitle track; completeness unverified')
            if not segments:
                # Probe ASR before downloading media; a subtitle network error never reaches this fallback.
                check = doctor()
                if not check['audio_ready']:
                    raise RuntimeError('Local audio transcription is unavailable. Run doctor for missing prerequisites; provide a transcript or configure the existing runtime/model.')
                audio = folder / 'audio.wav'
                if not audio.exists():
                    run(['yt-dlp', '--no-playlist', '-f', 'bestaudio/best', '-x', '--audio-format', 'wav', '-o', str(folder / 'audio.%(ext)s'), '--', args.source], timeout=1800)
        else:
            audio = local.resolve()
        if audio is not None:
            check = doctor()
            if not check['audio_ready']:
                raise RuntimeError('Local ASR prerequisites unavailable; run doctor. CPU is supported with a compatible runtime and sufficient RAM.')
            segments, details = transcribe(audio, folder, args, check)
            metadata.update(details)
        if not segments:
            raise ValueError('No usable transcript; inspect metadata and ASR logs')
        text = '\n\n'.join(segment['text'] for segment in segments) + '\n'
        temporary = transcript.with_suffix('.tmp')
        temporary.write_text(text, encoding='utf-8')
        temporary.replace(transcript)
        save(folder / 'segments.json', segments)
        metadata['status'] = 'partial' if metadata.get('gaps') else 'complete'
        metadata['transcript_sha256'] = digest(transcript)
        save(metadata_path, metadata)
        print(json.dumps({'status': metadata['status'], 'output': str(folder)}, ensure_ascii=False))
        return 2 if metadata['status'] == 'partial' else 0
    except BaseException as exc:
        metadata.update(status='failed', error=str(exc) or type(exc).__name__)
        save(metadata_path, metadata)
        raise


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor', help='Inspect installed tools, models and runtime; never install anything')
    fetch_parser = commands.add_parser('fetch', help='Acquire a transcript from a video URL, audio, TXT, VTT or SRT')
    fetch_parser.add_argument('source')
    fetch_parser.add_argument('--output', type=Path, required=True, help='Dedicated job directory; rerun same input to resume')
    fetch_parser.add_argument('--language', help='Spoken/caption language code, e.g. hi or en; no translation')
    fetch_parser.add_argument('--device', choices=('auto', 'cpu', 'gpu'), default='auto')
    fetch_parser.add_argument('--audio-only', action='store_true', help='Explicitly test audio fallback instead of URL subtitles')
    fetch_parser.add_argument('--chunk-seconds', type=int, choices=range(10, 121), default=60, metavar='10..120')
    return result


def main():
    args = parser().parse_args()
    try:
        if args.command == 'doctor':
            check = doctor()
            print(json.dumps(check, ensure_ascii=False, indent=2))
            return 0 if check['audio_ready'] else 2
        return fetch(args)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrupted; completed ASR chunks can be reused.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
