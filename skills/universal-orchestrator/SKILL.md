---
name: universal-orchestrator
description: Use when delegating bounded, verifiable coding work to a CLI model, then verifying and auditing the result before accepting it.
---

# Universal Orchestrator

A fast model does the typing, a strong model audits it, you decide. Delegate to
save tokens, never to save judgment.

Write the code yourself when the task is small, ambiguous, or faster to type
than to brief. Delegate only when the work is bounded, fully briefable, and
objectively verifiable — and keep architecture, diagnosis, and final acceptance.

## Loop

Runs as a uv script with no dependencies: the PEP 723 header pins Python >=3.12,
so `./orchestrator.py` works with no install and no venv. Plain
`python3 orchestrator.py` works too.

```bash
./orchestrator.py models              # installed CLIs
./orchestrator.py models codex        # live models and efforts
./orchestrator.py --help              # or --help on any subcommand
```

**1. Brief.** Write the template below to a file. It must stand alone — the body
starts cold in a detached worktree at `HEAD` with no conversation history.

**2. Run** the body. Each run gets a fresh worktree, so the user's working tree
is never touched and never needs to be clean.

```bash
./orchestrator.py run --selection codex:gpt-5.6-luna:low \
  --brief /abs/brief.md --repo /abs/repo
```

Prints a run directory holding `status.json` (files changed, tokens, cost),
`body.diff`, `body-report.txt`, and `raw.log`.

**3. Verify.** Run every verification command from the brief. Each executes in
the body's worktree and appends to `verification.json`.

```bash
./orchestrator.py verify --run-dir <run> --command 'pytest -q'
```

**4. Audit.** Sends the brief, verification results, and diff to a strong model.
Exits 0 on `PASS`, 1 on `FAIL` or `UNCLEAR`.

```bash
./orchestrator.py review --run-dir <run> --selection claude:opus:high
```

The instructions the auditor follows are the **Audit prompt** below — edit that
block to change what counts as a failure.

**5. Decide.** Read `body.diff` and `review.md` yourself. The audit is evidence,
not a verdict — a passing review of an out-of-scope diff is still a rejection.

**6. Repair once.** Write a focused repair brief and rerun with `--reuse <run>`
in the same worktree. One repair; then stop and report the evidence.

**7. Integrate and clean up.** `git apply` the diff, or work from the worktree,
then `./orchestrator.py cleanup --run-dir <run>`.

## Brief template

```markdown
# Objective
[One observable outcome.]

# Repository context
[Only the conventions and facts needed for this change.]

# Scope
- Allowed paths: [exact paths or narrow patterns]
- Required changes: [specific behavior]

# Exclusions
- Do not touch: [paths and behavior]
- No secrets, credential files, destructive database work, pushes, deployments,
  or external side effects.
- Do not commit, reset, clean, or stash.
- Implement directly. Do not stop to ask for approval or confirmation.

# Acceptance
- [Objective requirement]

# Verification
Run exactly:
- `[command]`

# Final report
Return: status; files changed; verification commands and results; concerns.
```

One task per brief. Name the allowed paths precisely — the auditor judges scope
against this text, so a vague `Allowed paths` makes the audit useless. If scope
or acceptance cannot be stated precisely, the work is not delegable.

A repair brief states the observed failure, not the whole task again: the
verification output, what it means, and the narrowest fix. The worktree still
holds the first attempt, so the diff stays cumulative.

## Audit prompt

`review` reads this block and substitutes `{brief}`, `{verification}`, and
`{diff}`. Change it here; nothing in `orchestrator.py` needs touching.

```text
You are auditing a code change another AI wrote. Judge it only against the
brief below.

First line must be exactly `VERDICT: PASS` or `VERDICT: FAIL`. Then list
concrete problems: where, what is wrong, which part of the brief it breaks.
Fail the change for scope violations (edits outside the allowed paths), unmet
acceptance criteria, bugs, or claims the verification output does not support.
Do not rewrite the code.

=== BRIEF ===
{brief}

=== VERIFICATION ===
{verification}

=== DIFF ===
{diff}
```

## Rules

- The body's report is not evidence. `status.ok` means only that the process
  exited cleanly, made no commit, and changed at least one file.
- An empty `changed_files` means the body stalled or asked a question — read
  `body-report.txt`, then fix the brief rather than rerunning it unchanged.
- Reject scope drift, body-created commits, and edits outside the allowed paths.
- Never auto-merge, push, deploy, or claim success before verification passes.
- Bodies run with the adapter's YOLO flag inside a throwaway worktree; reviewers
  never do. YOLO does not widen the user's authorized scope.
- `status.json` and `review.json` carry token counts and cost. If delegating
  costs more than doing it yourself would have, stop delegating that task shape.

## Adapters

`ADAPTERS` at the top of `orchestrator.py` holds everything CLI-specific: the
flags, and where the model list comes from — `models_file` for codex
(`~/.codex/models_cache.json`), `models_cmd` for opencode and agy. Names are
written down only for claude, which has no offline source (`claude models` is a
billed prompt, not a listing); its `models_static` lists the aliases
`opus`/`sonnet`/`haiku`/`fable` at efforts `low`…`max`, and full model ids work
too. Everywhere else an unknown model is rejected by the CLI, the only thing
that knows.

Adapters are argument arrays, never shell strings. `{model}`, `{effort}`,
`{repo}`, `{prompt}` are substituted; every other brace is literal. Order is
`cmd → yolo → model → effort → cwd → tail → prompt`, where `prompt` is `stdin`,
`argv`, or a template like `--print={prompt}`.

Two traps worth keeping: `agy --print` swallows the argument after it, so its
prompt must be attached, and `agy` bakes effort into the model slug
(`gemini-3.7-flash-high`). After editing a flag, check it with
`./orchestrator.py models <cli>` and one throwaway run.

Install by linking this folder into `~/.claude/skills/` or `~/.codex/skills/`.
