#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run a coding CLI in a throwaway worktree, then verify and review its diff."""

import argparse
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

MAX_DIFF_CHARS = 300_000
MAX_VERIFICATION_CHARS = 50_000
PLACEHOLDER = re.compile(r"\{(model|effort|repo|prompt)\}")
CACHE_KEYS = {
    "cached_tokens",
    "cache_read_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "cached_content_token_count",
    "cache_read",
    "cache_creation",
    "cache_write",
    "read",
    "creation",
}

# Everything CLI-specific lives here: how to invoke it, and where its model list
# comes from. Model names are not written down unless a CLI offers no way to ask
# (claude), so this table cannot go stale when a provider ships a model.
# Invocation order: cmd -> yolo -> model -> effort -> cwd -> tail -> prompt.
# {model} {effort} {repo} {prompt} are substituted; any other brace is literal.
ADAPTERS = {
    "codex": {
        "cmd": ["codex", "exec", "--ephemeral", "--json"],
        "yolo": ["--dangerously-bypass-approvals-and-sandbox"],
        "model": ["--model", "{model}"],
        "effort": ["--config", 'model_reasoning_effort="{effort}"'],
        "cwd": ["-C", "{repo}"],
        "tail": ["-"],
        "prompt": "stdin",
        "models_file": "~/.codex/models_cache.json",
    },
    "claude": {
        "cmd": ["claude", "--print", "--output-format", "json"],
        "yolo": ["--dangerously-skip-permissions"],
        "model": ["--model", "{model}"],
        "effort": ["--effort", "{effort}"],
        "prompt": "argv",
        # The only CLI with no offline model list — `claude models` is a billed
        # prompt, not a listing. These are aliases; full ids work too.
        "models_static": ["opus", "sonnet", "haiku", "fable"],
        "efforts_static": ["low", "medium", "high", "xhigh", "max"],
    },
    "opencode": {
        "cmd": ["opencode", "run", "--format", "json"],
        "yolo": ["--auto"],
        "model": ["--model", "{model}"],
        "effort": ["--variant", "{effort}"],
        "cwd": ["--dir", "{repo}"],
        "prompt": "argv",
        "models_cmd": ["opencode", "models"],
    },
    "agy": {
        "cmd": ["agy", "--output-format", "json"],
        "yolo": ["--dangerously-skip-permissions"],
        "model": ["--model", "{model}"],
        "effort": ["--effort", "{effort}"],
        # --print swallows the next argument, so the prompt must be attached.
        "prompt": "--print={prompt}",
        # Prints "slug<TAB>Display Name"; effort is baked into the slug.
        "models_cmd": ["agy", "models"],
    },
}


class Error(ValueError):
    """Invalid selection or repository state."""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], text=True, capture_output=True, check=True
    ).stdout


def _nul(output: str) -> list[str]:
    return [item for item in output.split("\0") if item]


def parse_selection(value: str) -> tuple[str, str, str | None]:
    parts = [part.strip() for part in value.split(":")]
    if len(parts) not in (2, 3) or not all(parts):
        raise Error("selection must be cli:model[:effort]")
    if parts[0] not in ADAPTERS:
        raise Error(f"CLI is not configured: {parts[0]}")
    return parts[0], parts[1], parts[2] if len(parts) == 3 else None


def resolve_repo(path: Path) -> Path:
    try:
        candidate = path.resolve(strict=True)
        top = Path(_git(candidate, "rev-parse", "--show-toplevel").strip()).resolve()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise Error(f"not a Git repository: {path}") from exc
    if top != candidate:
        raise Error(f"--repo must be the Git top level: {top}")
    return top


def build_command(
    adapter: dict, model: str, effort: str | None, cwd: Path, prompt: str, yolo: bool
) -> tuple[list[str], str | None]:
    values = {"model": model, "effort": effort or "", "repo": str(cwd), "prompt": prompt}

    def expand(parts: list[str]) -> list[str]:
        # Only the known placeholders; str.format would choke on the literal
        # braces in arguments like model_reasoning_effort="high".
        return [re.sub(PLACEHOLDER, lambda m: values[m.group(1)], part) for part in parts]

    command = expand(adapter["cmd"])
    if yolo:
        command += expand(adapter.get("yolo", []))
    command += expand(adapter.get("model", []))
    if effort:
        command += expand(adapter.get("effort", []))
    command += expand(adapter.get("cwd", [])) + expand(adapter.get("tail", []))
    mode = adapter.get("prompt", "argv")
    if mode == "stdin":
        return command, prompt
    if mode == "argv":
        return [*command, prompt], None
    return [*command, *expand([mode])], None


def _walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _documents(raw: str) -> list:
    documents = []
    for line in raw.splitlines():
        try:
            documents.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if documents:
        return documents
    # Not JSONL, so try the whole output as one document (claude, agy).
    try:
        return [json.loads(raw)]
    except json.JSONDecodeError:
        return []


def _token_counts(node: dict) -> dict | None:
    def number(key):
        value = node.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    for input_key, output_key in (("input_tokens", "output_tokens"), ("input", "output")):
        given, produced = number(input_key), number(output_key)
        if given is not None and produced is not None:
            # Some CLIs fold cache reads into input_tokens and some do not, so
            # report them separately rather than inventing a misleading total.
            cached = sum(
                value
                for key, value in {**node, **(node.get("cache") or {})}.items()
                if key.lower() in CACHE_KEYS and isinstance(value, int)
                and not isinstance(value, bool)
            )
            return {
                "input_tokens": given,
                "output_tokens": produced,
                "cached_tokens": cached,
                "total_tokens": given + produced,
            }
    return None


def extract_usage(raw: str) -> tuple[dict | None, float | None]:
    """Last token block and cost anywhere in the output, whatever the CLI calls them."""
    usage = cost = None
    for document in _documents(raw):
        for node in _walk(document):
            usage = _token_counts(node) or usage
            for key in ("total_cost_usd", "cost"):
                value = node.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    cost = value
    return usage, cost


def extract_report(raw: str) -> str:
    report = None
    for document in _documents(raw):
        for node in _walk(document):
            for key in ("result", "response", "text"):
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    report = value.strip()
    return (report or raw[-8000:].strip()) + "\n"


def invoke(
    command: list[str], cwd: Path, stdin: str | None, timeout: float
) -> tuple[int | None, bool, str]:
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as exc:
        return None, False, f"cannot launch {command[0]}: {exc}"
    try:
        out, err = process.communicate(input=stdin, timeout=timeout)
        return process.returncode, False, out + (f"\n{err}" if err else "")
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, err = process.communicate()
        return process.returncode, True, out + (f"\n{err}" if err else "")


def collect_diff(workspace: Path, start_commit: str) -> tuple[list[str], str]:
    # --no-renames so a rename reports both the old and new path; scope review
    # needs to see what disappeared, not just what appeared.
    tracked = _nul(
        _git(workspace, "diff", "--name-only", "--no-renames", "-z", start_commit)
    )
    untracked = _nul(_git(workspace, "ls-files", "-o", "--exclude-standard", "-z"))
    diff = _git(workspace, "diff", "--binary", "--no-ext-diff", start_commit)
    for relative in untracked:
        patch = subprocess.run(
            ["git", "-C", str(workspace), "diff", "--no-index", "--binary",
             "--", os.devnull, relative],
            text=True,
            capture_output=True,
            check=False,
        )
        diff += patch.stdout
    return sorted(set(tracked) | set(untracked)), diff


def _run_dir(repo: Path) -> Path:
    # Artifacts live under .git so the runner never shows up in the repo's own
    # git status, and the body cannot stumble into its audit trail.
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = repo / ".git" / "orchestrator" / f"run-{stamp}-{secrets.token_hex(3)}"
    path.mkdir(parents=True)
    return path


def _read_status(run_dir: Path) -> dict:
    try:
        return json.loads((run_dir.resolve(strict=True) / "status.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise Error(f"cannot read run: {exc}") from exc


def _workspace(run_dir: Path) -> Path:
    workspace = Path(_read_status(run_dir)["workspace"])
    if not workspace.is_dir():
        raise Error(f"workspace is gone (cleaned up?): {workspace}")
    return workspace


def run_body(
    selection: str,
    brief_path: Path,
    repo_path: Path,
    timeout: float,
    reuse: Path | None = None,
) -> Path:
    cli, model, effort = parse_selection(selection)
    if shutil.which(ADAPTERS[cli]["cmd"][0]) is None:
        raise Error(f"CLI is not installed: {ADAPTERS[cli]['cmd'][0]}")
    repo = resolve_repo(repo_path)
    try:
        brief = brief_path.resolve(strict=True).read_text()
    except OSError as exc:
        raise Error(f"cannot read brief: {exc}") from exc

    run_dir = _run_dir(repo)
    if reuse is not None:
        workspace = (reuse.resolve() / "worktree").resolve()
        if not (workspace / ".git").exists():
            raise Error(f"no reusable worktree at {workspace}")
    else:
        workspace = run_dir / "worktree"
        try:
            _git(repo, "worktree", "add", "--detach", str(workspace), "HEAD")
        except subprocess.CalledProcessError as exc:
            raise Error(f"cannot create worktree: {exc.stderr.strip()}") from exc
    start_commit = _git(workspace, "rev-parse", "HEAD").strip()

    command, stdin = build_command(
        ADAPTERS[cli], model, effort, workspace, brief, yolo=True
    )
    started = time.monotonic()
    exit_code, timed_out, raw = invoke(command, workspace, stdin, timeout)
    elapsed = round(time.monotonic() - started, 3)

    changed, diff = collect_diff(workspace, start_commit)
    body_committed = _git(workspace, "rev-parse", "HEAD").strip() != start_commit
    usage, cost = extract_usage(raw)
    (run_dir / "brief.md").write_text(brief)
    (run_dir / "raw.log").write_text(raw)
    (run_dir / "body-report.txt").write_text(extract_report(raw))
    (run_dir / "body.diff").write_text(diff)
    status = {
        # An empty diff is a failure: the body stalled, refused, or asked a
        # question instead of working. Exiting 0 is not evidence of work.
        "ok": bool(
            exit_code == 0 and not timed_out and not body_committed and changed
        ),
        "cli": cli,
        "model": model,
        "effort": effort,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "elapsed_seconds": elapsed,
        "repo": str(repo),
        "workspace": str(workspace),
        "start_commit": start_commit,
        "body_committed": body_committed,
        "changed_files": changed,
        "usage": usage,
        "cost_usd": cost,
    }
    (run_dir / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    return run_dir


def verify(run_dir: Path, command: str, timeout: float) -> int:
    """Run one of the brief's verification commands in the body's worktree."""
    if not command.strip():
        raise Error("verification command must not be empty")
    workspace = _workspace(run_dir)
    # shell=True: verification commands come from the brain, which can already
    # run anything it likes; pipes and && are common enough to be worth it.
    try:
        proc = subprocess.run(
            command, shell=True, cwd=workspace, text=True,
            capture_output=True, timeout=timeout,
        )
        exit_code, output = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        exit_code, output = 124, f"timed out after {timeout}s"
    path = run_dir / "verification.json"
    entries = json.loads(path.read_text()) if path.exists() else []
    entries.append({
        "command": command,
        "exit_code": exit_code,
        "passed": exit_code == 0,
        "output": output[-20_000:],
        "recorded_at": datetime.now(UTC).isoformat(),
    })
    path.write_text(json.dumps(entries, indent=2) + "\n")
    print(output, end="")
    return exit_code


def _cap(text: str, limit: int, label: str) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n[{label} truncated; read the run directory]\n"


def audit_prompt(brief: str, verification: str, diff: str) -> str:
    """What counts as a failing change is policy, so it lives in SKILL.md where
    the brain can read and edit it without touching this script."""
    skill = Path(__file__).with_name("SKILL.md")
    try:
        text = skill.read_text()
    except OSError as exc:
        raise Error(f"cannot read {skill}: {exc}") from exc
    section_match = re.search(r"^## Audit prompt\b.*?(?=\n## |\Z)", text, re.S | re.M)
    if not section_match:
        raise Error(f"{skill} has no '## Audit prompt' section")
    match = re.search(r"^```[a-z]*\n(.*)\n```\s*$", section_match.group(0), re.S | re.M)
    if not match:
        raise Error(f"{skill} has no '## Audit prompt' fenced block")
    prompt = match.group(1)
    for name, value in ("brief", brief), ("verification", verification), ("diff", diff):
        prompt = prompt.replace("{" + name + "}", value)
    return prompt


def review(run_dir: Path, selection: str, timeout: float) -> str:
    """Hand the brief, verification results, and diff to an auditing model."""
    cli, model, effort = parse_selection(selection)
    run_dir = run_dir.resolve(strict=True)
    workspace = _workspace(run_dir)
    diff = (run_dir / "body.diff").read_text()
    if not diff.strip():
        raise Error("nothing to review: body.diff is empty")
    verification_path = run_dir / "verification.json"
    prompt = audit_prompt(
        brief=(run_dir / "brief.md").read_text(),
        verification=(
            _cap(verification_path.read_text(), MAX_VERIFICATION_CHARS, "verification")
            if verification_path.exists()
            else "none recorded — treat every claim in the change as unverified"
        ),
        diff=_cap(diff, MAX_DIFF_CHARS, "diff"),
    )
    command, stdin = build_command(
        ADAPTERS[cli], model, effort, workspace, prompt, yolo=False
    )
    exit_code, timed_out, raw = invoke(command, workspace, stdin, timeout)
    report = extract_report(raw)
    match = re.search(r"VERDICT:\s*(PASS|FAIL)", report, re.IGNORECASE)
    verdict = match.group(1).upper() if match else "UNCLEAR"
    usage, cost = extract_usage(raw)
    (run_dir / "review-raw.log").write_text(raw)
    (run_dir / "review.md").write_text(report)
    (run_dir / "review.json").write_text(
        json.dumps(
            {
                "verdict": verdict,
                "cli": cli,
                "model": model,
                "effort": effort,
                "exit_code": exit_code,
                "timed_out": timed_out,
                "usage": usage,
                "cost_usd": cost,
            },
            indent=2,
        )
        + "\n"
    )
    print(report, end="")
    return verdict


def list_models(cli: str) -> list[tuple[str, list[str]]]:
    """Ask the CLI itself, so no model list here can go stale."""
    adapter = ADAPTERS[cli]
    if path := adapter.get("models_file"):
        cache = Path(path).expanduser()
        try:
            models = json.loads(cache.read_text())["models"]
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise Error(f"cannot read {cache}: {exc}") from exc
        return [
            (m["slug"], [e["effort"] for e in m.get("supported_reasoning_levels", [])])
            for m in models
        ]
    if command := adapter.get("models_cmd"):
        try:
            out = subprocess.run(
                command, text=True, capture_output=True, check=True, timeout=120
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            raise Error(f"cannot list {cli} models: {exc}") from exc
        # agy prints "slug<TAB>Display Name"; opencode prints bare slugs.
        return [(line.split("\t")[0].strip(), []) for line in out.splitlines() if line.strip()]
    efforts = adapter.get("efforts_static", [])
    return [(name, efforts) for name in adapter["models_static"]]


def cleanup(run_dir: Path) -> None:
    status = _read_status(run_dir)
    workspace = Path(status["workspace"])
    if not workspace.exists():
        return
    try:
        _git(Path(status["repo"]), "worktree", "remove", "--force", str(workspace))
    except subprocess.CalledProcessError as exc:
        raise Error(f"cannot remove worktree: {exc.stderr.strip()}") from exc


def _models_command(cli: str | None) -> int:
    installed = [
        name for name, a in ADAPTERS.items() if shutil.which(a["cmd"][0]) is not None
    ]
    if cli is None:
        print("\n".join(installed) or "no configured CLI is installed")
        return 0
    if cli not in ADAPTERS:
        raise Error(f"CLI is not configured: {cli}")
    if cli not in installed:
        raise Error(f"CLI is not installed: {cli}")
    for model, efforts in list_models(cli):
        print(f"{cli}:{model}" + (f"  efforts={','.join(efforts)}" if efforts else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="subcommand", required=True)
    # dest="subcommand", not "command": `verify --command` would overwrite it.
    models = sub.add_parser("models", help="list what a CLI actually supports")
    models.add_argument("cli", nargs="?")
    run = sub.add_parser("run", help="run one body attempt in a worktree")
    run.add_argument("--selection", required=True, help="cli:model[:effort]")
    run.add_argument("--brief", type=Path, required=True)
    run.add_argument("--repo", type=Path, required=True)
    run.add_argument("--timeout", type=float, default=1200)
    run.add_argument("--reuse", type=Path, help="repair in an earlier run's worktree")
    check = sub.add_parser("verify", help="run a verification command in the worktree")
    check.add_argument("--run-dir", type=Path, required=True)
    check.add_argument("--command", required=True)
    check.add_argument("--timeout", type=float, default=600)
    audit = sub.add_parser("review", help="have an auditing model judge the diff")
    audit.add_argument("--run-dir", type=Path, required=True)
    audit.add_argument("--selection", required=True, help="cli:model[:effort]")
    audit.add_argument("--timeout", type=float, default=900)
    remove = sub.add_parser("cleanup", help="remove a run's worktree")
    remove.add_argument("--run-dir", type=Path, required=True)

    args = parser.parse_args(argv)
    match args.subcommand:
        case "models":
            return _models_command(args.cli)
        case "run":
            run_dir = run_body(
                args.selection, args.brief, args.repo, args.timeout, args.reuse
            )
            print(run_dir)
            return 0 if _read_status(run_dir)["ok"] else 1
        case "verify":
            return 0 if verify(args.run_dir, args.command, args.timeout) == 0 else 1
        case "review":
            return 0 if review(args.run_dir, args.selection, args.timeout) == "PASS" else 1
        case "cleanup":
            cleanup(args.run_dir)
            return 0
    raise Error(f"unknown command: {args.subcommand}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
