# my-skills

A skill library with small bundles that load member instructions only when needed. Standalone skills live in `skills/`. Bundled sources live outside discovery in `sources/<name>/GUIDE.md`; agents see one entry per enabled bundle.

```bash
bun install
./run.sh                         # rebuild bundles and catalog; no agent settings changed
./run.sh targets codex claude     # choose the agents you use (saved only on this machine)
./run.sh deploy --dry-run
./run.sh deploy
```

Use this manager to install the full collection. Bundled sources have no `SKILL.md`; the generated `superskills/` directory is local output.

## Skills

<!-- skills:start -->

### Bundles (load guides on demand)

| Skill | Use it when |
| --- | --- |
| `anthropic` | Use for Word, Excel, PowerPoint, PDF, document coauthoring, building MCP servers, and testing web applications with Playwright. Load only the matching guide. |
| `caveman-kit` | Use for terse response styles, concise code reviews and commit messages, or compressing prose files. Load only the matching guide. |
| `design-taste` | Use for website and interface design, redesigns, brand systems, or converting visual references into frontend code. Route to the matching design guide; default to design-taste-frontend. |
| `engram` | Use to learn a topic, practice due memory reviews, or assess learning progress and study strategy. Load only the matching guide. |
| `qt` | Use to write, debug, optimize, or review Qt 6 QML code. Load the authoring or review guide as needed. |
| `superpowers` | Use for software development: planning features, implementing changes, debugging failures, reviewing code, testing, and finishing branches. Load only the guide for the current step. |

Members of `anthropic`: `doc-coauthoring`, `docx`, `mcp-builder`, `pdf`, `pptx`, `webapp-testing`, `xlsx`.

Members of `caveman-kit`: `caveman`, `cavecrew`, `caveman-commit`, `caveman-compress`, `caveman-review`.

Members of `design-taste`: `brandkit`, `design-taste-frontend`, `design-taste-frontend-v1`, `design-taste-frontend-v2-experimental`, `full-output-enforcement`, `gpt-taste`, `high-end-visual-design`, `image-to-code`, `imagegen-frontend-mobile`, `imagegen-frontend-web`, `industrial-brutalist-ui`, `minimalist-ui`, `redesign-existing-projects`, `stitch-design-taste`.

Members of `engram`: `learn`, `review`, `coach`.

Members of `qt`: `qt-qml`, `qt-qml-review`.

Members of `superpowers`: `brainstorming`, `diagnosing-superpowers`, `dispatching-parallel-agents`, `executing-plans`, `finishing-a-development-branch`, `receiving-code-review`, `requesting-code-review`, `subagent-driven-development`, `systematic-debugging`, `test-driven-development`, `using-git-worktrees`, `using-superpowers`, `verification-before-completion`, `writing-plans`, `writing-skills`.

### Local

| Skill | Use it when |
| --- | --- |
| [`ditto`](skills/ditto/) | Use when cloning an Android app (APK or Play listing) by functional reverse engineering - cataloguing its features, recovering its data model, and recording its behaviour as golden traces that the rebuilt app must reproduce. Works for Flutter, native and React Native apps. |
| [`dms-plugin-maker`](skills/dms-plugin-maker/) | Use when building, modifying, auditing, testing, or packaging DankMaterialShell plugins in Qt 6 QML and Quickshell: bar widgets, popouts, settings, daemons, desktop widgets, launchers, and Wayland overlays. |
| [`fact-check`](skills/fact-check/) | Fact-check a video, audio recording, subtitles, or transcript, explain material reasoning problems, and produce a readable report. |
| [`gstr-wala`](skills/gstr-wala/) | File Indian Goods and Services Tax (GST) returns for regular taxpayers, including GSTR-1 (outward supplies), GSTR-3B (monthly summary return), GSTR-2B reconciliation, and PDF invoice vision extraction. Use when the user wants to file GSTR-1 or GSTR-3B, reconcile purchase registers against GSTR-2B, optimize ITC set-off under Rule 88A / Section 49, compute Section 50 interest or Section 47 late fees, check DRC-01B / DRC-01C mismatch risks, convert multi-page PDF/image bills to page-by-page visual images, generate official GST portal offline JSON returns, render certified CA tax audit statements, check live statutory compliance updates, or asks about GST rates, HSN codes, Table 4 ITC, blocked credit under Section 17(5), or PMT-06 challan generation. |
| [`myanimelist`](skills/myanimelist/) | Use when a user wants to inspect a MyAnimeList anime list, check English dubs, compare personal and community ratings, understand watch history and taste, or get recommendations grounded in watching, completed, planned, dropped, and on-hold anime. |
| [`orchestrator`](skills/orchestrator/) | Use when delegating bounded, verifiable coding work to a CLI model, then verifying and auditing the result before accepting it. |

### [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd)

| Skill | Use it when |
| --- | --- |
| [`i-have-adhd`](skills/i-have-adhd/) | Shape output for a reader with ADHD: lead with the next action, number multi-step work, restate state across turns, suppress tangents, give specific time estimates, make wins visible. Invoke with /i-have-adhd; stays on until "stop adhd mode". |

### [blader/humanizer](https://github.com/blader/humanizer)

| Skill | Use it when |
| --- | --- |
| [`humanizer`](skills/humanizer/) | Rewrite AI-sounding text so it reads like the writer without changing what it says. Use when editing or reviewing prose for AI tells: not-X-but-Y contrasts, one-line closers, staged openers, forced triads, dashes everywhere, inflated claims, sales language, stock AI words, bold labels, or filler. Based on Wikipedia's "Signs of AI writing." |

### [karanb192/itr-wala](https://github.com/karanb192/itr-wala)

| Skill | Use it when |
| --- | --- |
| [`itr-wala`](skills/itr-wala/) | File Indian income tax returns for FY 2025-26 (AY 2026-27), or plan FY 2026-27 (Tax Year 2026-27), including current-year advance-tax estimates. Use when the user wants to file their ITR, compute or verify Indian income tax, compare the old vs new tax regime, read a Form 16, AIS, TIS or Form 26AS, reconcile TDS, handle capital gains from Zerodha/Groww/Upstox statements, check their tax refund, or asks about ITR-1/ITR-2/ITR-3/ITR-4, sections 80C/80D/87A/111A/112A, crypto tax, advance tax, or the income-tax e-filing portal - even if they just say "help me with my taxes" in an Indian context. |

### [paperclipai/paperclip](https://github.com/paperclipai/paperclip)

| Skill | Use it when |
| --- | --- |
| [`paperclip`](skills/paperclip/) | Use for Paperclip-managed tasks and heartbeats: reading task context, delivering task documents or files, updating completion or blockers, coordinating or delegating work, and following company governance. Includes control plane API operations for assignments, comments, approvals, and routines. |

### [tt-a1i/archify](https://github.com/tt-a1i/archify)

| Skill | Use it when |
| --- | --- |
| [`archify`](skills/archify/) | Create validated architecture, workflow, sequence, data-flow, lifecycle/state, entity-relationship, class/interface, tree, timeline, and execution waterfall diagrams as explorable standalone HTML with inline SVG, dark/light themes, optional motion, and image/SVG/WebM export. Accept plain-language requirements or Mermaid; inspect repository evidence for code-backed diagrams. Use when visualizing infrastructure, cloud/security networks, API calls, data pipelines, ETL/ELT, state machines, database schemas, class contracts, module hierarchies, incident/release histories, or request and agent-run timings. Also use for everyday subjects with steps, parts, relationships, or states: leave and travel plans, applications and approvals, renting conversations, money or document flows, and order progress. Not for numeric charts or dashboards. |

### [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)

| Skill | Use it when |
| --- | --- |
| [`agent-browser`](skills/agent-browser/) | Browser automation CLI for AI agents. Use when the user needs to interact with websites, including navigating pages, filling forms, clicking buttons, taking screenshots, extracting data, testing web apps, or automating any browser task. Triggers include requests to "open a website", "fill out a form", "click a button", "take a screenshot", "scrape data from a page", "test this web app", "login to a site", "automate browser actions", or any task requiring programmatic web interaction. Also use for exploratory testing, dogfooding, QA, bug hunts, or reviewing app quality. Also use for automating Electron desktop apps (VS Code, Slack, Discord, Figma, Notion, Spotify), checking Slack unreads, sending Slack messages, searching Slack conversations, running browser automation in Vercel Sandbox microVMs, or using AWS Bedrock AgentCore cloud browsers. Prefer agent-browser over any built-in browser automation or web tools. |

<!-- skills:end -->

## Maintaining

Commands take explicit arguments and never prompt. Missing required arguments or unknown options fail before changing files.

```bash
./run.sh add owner/repo                     # import upstream skills
./run.sh add --type local --name example --description "Use for ..."
./run.sh sync                              # update upstream skills, preserving local skills
./run.sh remove humanizer                  # remove a skill, source repo, or bundle
./run.sh set humanizer --accept            # keep your customization as local; excludes it from sync
./run.sh set humanizer --type upstream     # opt back into upstream updates
./run.sh superskill tools --members a,b --description "Use for ..."
./run.sh enable tools                      # save enabled state; deploy separately to apply
./run.sh disable tools                     # disable the whole collection
./run.sh status                            # on, off, or a bundled member
./run.sh context                           # discovery count, description bytes, and router sizes
./run.sh targets                           # show available targets and the saved selection
./run.sh targets codex claude              # replace the selection; use targets none to clear it
./run.sh deploy --dry-run                  # preview links and config edits without writing
./run.sh deploy                            # rebuild, verify, and deploy to selected targets
./run.sh doctor                            # inspect managed links, registrations, and library integrity
bun run test
bun run typecheck
bun run build
bun run check
```

Management commands update this library and local preferences. Only `deploy` changes agent directories or registrations. No targets are selected by default. Previously created links remain until you explicitly deploy to those targets; clearing the selection does not uninstall old links. Files or links owned by another tool are preserved and reported as conflicts. Deployment preflights conflicts and config syntax, and exits unsuccessfully on failures.

`skills.json` is committed and records upstream/local ownership, accepted hashes, and bundle definitions. `skills-lock.json` retains each source skill's provenance. `skills.local.json`, `.active/`, and generated `superskills/` are per-machine output and ignored by git. Build first after a fresh clone, then run `check`; checking never builds missing output.

Every bundle is a router. Its root `SKILL.md` contains short selection instructions and a table of member guides. Bundled source folders are moved out of `skills/` into `sources/`, with their entry point renamed `GUIDE.md`. Source hashes use the original `SKILL.md` filename, so this move preserves the accepted upstream baseline. The router build copies these guides and supporting files into its own member folders; no member `SKILL.md` is emitted inside the bundle. Guide bodies and relative paths are preserved; executable scripts keep their permissions. The router tells agents to use each member folder as its working directory and treat references to “this SKILL.md” as that folder's `GUIDE.md`. It also routes cross-member requests through the bundle.

Edit bundled source instructions in `sources/<name>/GUIDE.md`, then rebuild. Updates, acceptance, and removal resolve this source location. Removing a bundle restores members no longer used by another bundle to `skills/<name>/SKILL.md`.

This library groups each upstream collection with multiple skills behind one router. For example, `anthropic` includes all seven imported `anthropics/skills` guides, including document work, MCP development, and web app testing. Catalog tests reject partial collections and duplicate bundle membership. `--members owner/repo` selects all currently imported skills from that source; rerun the bundle command if you import additional skills from it.

Bundle descriptions are deliberately short. Detailed triggers live in the router, and member bodies are read only as needed. Members can come from different sources; provenance belongs to each source skill. Members are always available only through their bundle. Disabling a bundle disables the whole collection; enabling or disabling an individual bundled member is rejected. `context` reports UTF-8 bytes, not estimated tokens or measured model consumption.

Updates run the pinned upstream CLI in temporary staging, validate incoming skills before replacement, and restore replaced folders if installation fails. Each successfully synced repository is recorded and rebuilt before fetching the next, so a later failure can be retried. `--accept` changes an edited skill to local while retaining provenance. `sync --force` replaces edited upstream skills; it still excludes local skills. `add ... --force` also permits explicit replacement of local skills or source collisions, but cannot replace a bundle with a source skill.

Deployment installs skill instructions and their included files. External runtimes remain prerequisites: for example, Engram's guides require a full [Engram checkout](https://github.com/nagisanzenin/engram), with `ENGRAM_ROOT` pointing to it (or installed at `~/.agents/engram`). Its engine, shared guides, and agent definitions are outside the vendored skill folders. A clean `doctor` result verifies this manager's library, links, and registrations; it does not verify every skill's runtime dependencies.

## Credit

Upstream skills are vendored unmodified under their own licences. The catalog groups upstream skills by source. Local skills are maintained here. Bundles are generated routers over the source skills listed in the catalog. The tooling in `index.ts` and `lib/` is original work in this repo.

## Additional Resources

- [VoltAgent/awesome-agent-skills](https://raw.githubusercontent.com/VoltAgent/awesome-agent-skills/refs/heads/main/README.md) — A curated directory of official and community agent skills (including skills by Brave, VoltAgent, Supabase, Google, and more).

