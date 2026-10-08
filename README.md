# my-skills

A curated collection of agent skills. Each one is a real folder in `skills/` — read its `SKILL.md` directly, or install the lot:

```bash
bunx skills add quantavil/my-skills --all
```

Ditto is maintained in this repository. Install it alone with `bunx skills add quantavil/my-skills --skill ditto`. Its evidence workflow covers Android/iOS inspection, Flutter reconstruction, and differential validation. Local skills are excluded from upstream sync.

## Skills

<!-- skills:start -->

### ./quantavil/my-skills

| Skill | Use it when |
| --- | --- |
| [`design-taste`](skills/design-taste/) | Master skill for premium interface taste and frontend art direction: anti-slop landing pages and redesigns, minimalist/brutalist/brand/Stitch style systems, image-first web and mobile concept direction, image-to-code builds, and complete untruncated output. Use when the user wants a distinctive website or landing page, a redesign or taste audit, a brand board, app-screen concepts, or design references generated before code. |
| [`ditto2`](skills/ditto2/) | Use when collecting evidence from an Android Flutter APK for cloning with Ditto2, or continuing a Ditto2 reconstruction from that evidence. |
| [`dms-plugin-maker`](skills/dms-plugin-maker/) | Use when building, modifying, auditing, testing, or packaging DankMaterialShell plugins in Qt 6 QML and Quickshell: bar widgets, popouts, settings, daemons, desktop widgets, launchers, and Wayland overlays. |
| [`fact-check`](skills/fact-check/) | Use when the user wants to fact-check a video, audio recording, subtitles, or transcript. |
| [`flutter-dart`](skills/flutter-dart/) | Master skill for Dart and Flutter development. Covers architecture best practices, UI and responsive layouts, layout debugging (RenderFlex overflow), declarative routing (go_router), localization (l10n/i18n), REST API integration (http), JSON serialization, unit/widget/integration testing (package:test, WidgetTester, package:checks, mockito), static analysis, runtime error debugging, FFI and native assets (ffigen, hooks), CLI apps, documentation, doc-code examples, and file path handling (package:path). |
| [`gstr-wala`](skills/gstr-wala/) | File Indian Goods and Services Tax (GST) returns for regular taxpayers, including GSTR-1 (outward supplies), GSTR-3B (monthly summary return), GSTR-2B reconciliation, and PDF invoice vision extraction. Use when the user wants to file GSTR-1 or GSTR-3B, reconcile purchase registers against GSTR-2B, optimize ITC set-off under Rule 88A / Section 49, compute Section 50 interest or Section 47 late fees, check DRC-01B / DRC-01C mismatch risks, convert multi-page PDF/image bills to page-by-page visual images, generate official GST portal offline JSON returns, render certified CA tax audit statements, check live statutory compliance updates, or asks about GST rates, HSN codes, Table 4 ITC, blocked credit under Section 17(5), or PMT-06 challan generation. |
| [`myanimelist`](skills/myanimelist/) | Use when a user wants to inspect a MyAnimeList anime list, check English dubs, compare personal and community ratings, understand watch history and taste, or get recommendations grounded in watching, completed, planned, dropped, and on-hold anime. |
| [`orchestrator`](skills/orchestrator/) | Use when delegating bounded, verifiable coding work to a CLI model, then verifying and auditing the result before accepting it. |

### [./skills/ditto](https://github.com/quantavil/my-skills/tree/main/skills/ditto)

| Skill | Use it when |
| --- | --- |
| [`ditto`](skills/ditto/) | Reconstruct an Android app in Flutter from an APK and runtime evidence, or review a Flutter clone for visual and behavioral parity. The supplied MCP backend supports Android emulators and ARM64 Flutter AOT analysis; iOS and other package formats need a separate capability contract. |

### [anthropics/skills](https://github.com/anthropics/skills)

| Skill | Use it when |
| --- | --- |
| [`algorithmic-art`](skills/algorithmic-art/) | Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration. Use this when users request creating art using code, generative art, algorithmic art, flow fields, or particle systems. Create original algorithmic art rather than copying existing artists' work to avoid copyright violations. |
| [`canvas-design`](skills/canvas-design/) | Create beautiful visual art in .png and .pdf documents using design philosophy. You should use this skill when the user asks to create a poster, piece of art, design, or other static piece. Create original visual designs, never copying existing artists' work to avoid copyright violations. |
| [`doc-coauthoring`](skills/doc-coauthoring/) | Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documentation, proposals, technical specs, decision docs, or similar structured content. This workflow helps users efficiently transfer context, refine content through iteration, and verify the doc works for readers. Trigger when user mentions writing docs, creating proposals, drafting specs, or similar documentation tasks. |
| [`docx`](skills/docx/) | Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx files) or Word templates (.dotx files). Triggers include: any mention of 'Word doc', 'word document', '.docx', '.dotx', or requests to produce professional documents with formatting like tables of contents, headings, page numbers, or letterheads. Also use when extracting or reorganizing content from .docx or .dotx files, inserting or replacing images in documents, performing find-and-replace in Word files, working with tracked changes or comments, or converting content into a polished Word document. If the user asks for a 'report', 'memo', 'letter', 'template', or similar deliverable as a Word or .docx file, use this skill. Do NOT use for PDFs, spreadsheets, Google Docs, or general coding tasks unrelated to document generation. |
| [`frontend-design`](skills/frontend-design/) | Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic direction, typography, and making choices that don't read as templated defaults. |
| [`mcp-builder`](skills/mcp-builder/) | Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services through well-designed tools. Use when building MCP servers to integrate external APIs or services, whether in Python (FastMCP) or Node/TypeScript (MCP SDK). |
| [`pdf`](skills/pdf/) | Use this skill whenever the user wants to do anything with PDF files. This includes reading or extracting text/tables from PDFs, combining or merging multiple PDFs into one, splitting PDFs apart, rotating pages, adding watermarks, creating new PDFs, filling PDF forms, encrypting/decrypting PDFs, extracting images, and OCR on scanned PDFs to make them searchable. If the user mentions a .pdf file or asks to produce one, use this skill. |
| [`pptx`](skills/pptx/) | Use this skill any time a .pptx or .potx file is involved in any way — as input, output, or both. This includes: creating slide decks, pitch decks, or presentations; reading, parsing, or extracting text from any .pptx or .potx file (even if the extracted content will be used elsewhere, like in an email or summary); editing, modifying, or updating existing presentations; combining or splitting slide files; working with templates (.potx), layouts, speaker notes, or comments. Trigger whenever the user mentions "deck," "slides," "presentation," or references a .pptx or .potx filename, regardless of what they plan to do with the content afterward. If a .pptx or .potx file needs to be opened, created, or touched, use this skill. |
| [`theme-factory`](skills/theme-factory/) | Toolkit for styling artifacts with a theme. These artifacts can be slides, docs, reportings, HTML landing pages, etc. There are 10 pre-set themes with colors/fonts that you can apply to any artifact that has been creating, or can generate a new theme on-the-fly. |
| [`webapp-testing`](skills/webapp-testing/) | Toolkit for interacting with and testing local web applications using Playwright. Supports verifying frontend functionality, debugging UI behavior, capturing browser screenshots, and viewing browser logs. |
| [`xlsx`](skills/xlsx/) | Use this skill any time a spreadsheet file is the primary input or output. This means any task where the user wants to: open, read, edit, or fix an existing .xlsx, .xlsm, .xltx, .csv, or .tsv file (e.g., adding columns, computing formulas, formatting, charting, cleaning messy data); create a new spreadsheet from scratch or from other data sources; or convert between tabular file formats. Trigger especially when the user references a spreadsheet file by name or path — even casually (like "the xlsx in my downloads") — and wants something done to it or produced from it. Also trigger for cleaning or restructuring messy tabular data files (malformed rows, misplaced headers, junk data) into proper spreadsheets. The deliverable must be a spreadsheet file. Do NOT trigger when the primary deliverable is a Word document, HTML report, standalone Python script, database pipeline, or Google Sheets API integration, even if tabular data is involved. |

### [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd)

| Skill | Use it when |
| --- | --- |
| [`i-have-adhd`](skills/i-have-adhd/) | Shape output for a reader with ADHD: lead with the next action, number multi-step work, restate state across turns, suppress tangents, give specific time estimates, make wins visible. Invoke with /i-have-adhd; stays on until "stop adhd mode". |

### [blader/humanizer](https://github.com/blader/humanizer)

| Skill | Use it when |
| --- | --- |
| [`humanizer`](skills/humanizer/) | Rewrite AI-sounding text so it reads like the writer without changing what it says. Use when editing or reviewing prose for AI tells: not-X-but-Y contrasts, one-line closers, staged openers, forced triads, dashes everywhere, inflated claims, sales language, stock AI words, bold labels, or filler. Based on Wikipedia's "Signs of AI writing." |

### [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman)

| Skill | Use it when |
| --- | --- |
| [`cavecrew`](skills/cavecrew/) | When to delegate to `cavecrew-investigator` (locate code), `cavecrew-builder` (1-2 file edit) or `cavecrew-reviewer` (diff review) instead of working inline or using `Explore`. Their output is compressed, so main context lasts longer. |
| [`caveman`](skills/caveman/) | Ultra-compressed communication mode that cuts output tokens while keeping technical accuracy. Levels: lite, full, ultra and the wenyan variants. Use for /caveman, "caveman mode", "talk like caveman", "be brief" or "less tokens". |
| [`caveman-commit`](skills/caveman-commit/) | Write a Conventional Commits message compressed to intent only. Use for "write a commit", "commit message", /commit or /caveman-commit. |
| [`caveman-compress`](skills/caveman-compress/) | Compress a memory file such as CLAUDE.md or a todo list into caveman format to save input tokens, keeping a readable backup. Trigger: /caveman-compress. |
| [`caveman-review`](skills/caveman-review/) | Compressed code review - one line per finding with location, problem and fix. Use for /caveman-review, "review this PR", or "review the diff". |

### [karanb192/itr-wala](https://github.com/karanb192/itr-wala)

| Skill | Use it when |
| --- | --- |
| [`itr-wala`](skills/itr-wala/) | File Indian income tax returns (ITR) for FY 2025-26 / AY 2026-27. Use when the user wants to file their ITR, compute or verify Indian income tax, compare the old vs new tax regime, read a Form 16, AIS, TIS or Form 26AS, reconcile TDS, handle capital gains from Zerodha/Groww/Upstox statements, check their tax refund, or asks about ITR-1/ITR-2/ITR-3/ITR-4, sections 80C/80D/87A/111A/112A, crypto tax, advance tax, or the income-tax e-filing portal - even if they just say "help me with my taxes" in an Indian context. |

### [nagisanzenin/engram](https://github.com/nagisanzenin/engram)

| Skill | Use it when |
| --- | --- |
| [`coach`](skills/coach/) | Learning telemetry, strategy, and schedule — retention stats, calibration, grader audit, n-of-1 experiments, HTML dashboard. Use for "how am I doing", weekly check-ins, strategy questions, auditing the grader, or adjusting how Engram teaches. |
| [`learn`](skills/learn/) | Learn any topic properly — first-principles curriculum, generation-first tutoring, verified free recall, FSRS scheduling. Use when the user wants to learn, understand, study, or continue studying something. |
| [`review`](skills/review/) | Clear due memory reviews with free recall — the two-minute habit that makes learning permanent. Use when reviews are due, or the user wants to review, practice, or "do my engram reviews". |

### [Nutlope/hallmark](https://github.com/Nutlope/hallmark)

| Skill | Use it when |
| --- | --- |
| [`hallmark`](skills/hallmark/) | Anti-AI-slop design skill for greenfield pages, audits, redesigns, and design extraction from URLs or screenshots. Use when the user asks to build a new app or landing page, wants to redesign something, invokes Hallmark by name, or uses audit/redesign/study. |

### [obra/superpowers](https://github.com/obra/superpowers)

| Skill | Use it when |
| --- | --- |
| [`brainstorming`](skills/brainstorming/) | You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation. |
| [`dispatching-parallel-agents`](skills/dispatching-parallel-agents/) | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies |
| [`executing-plans`](skills/executing-plans/) | Use when executing an implementation plan in the current session as the implementer yourself — your human partner chose inline execution, or no subagent tool is available |
| [`finishing-a-development-branch`](skills/finishing-a-development-branch/) | Use when implementation is complete, all tests pass, and you need to decide how to integrate the work |
| [`receiving-code-review`](skills/receiving-code-review/) | Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires technical rigor and verification, not performative agreement or blind implementation |
| [`requesting-code-review`](skills/requesting-code-review/) | Use when completing tasks, implementing major features, or before merging to verify work meets requirements |
| [`subagent-driven-development`](skills/subagent-driven-development/) | Use when executing implementation plans with independent tasks in the current session |
| [`systematic-debugging`](skills/systematic-debugging/) | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes |
| [`test-driven-development`](skills/test-driven-development/) | Use when implementing any feature or bugfix, before writing implementation code |
| [`using-git-worktrees`](skills/using-git-worktrees/) | Use when starting feature work that needs isolation from current workspace or before executing implementation plans - ensures an isolated workspace exists via native tools or git worktree fallback |
| [`using-superpowers`](skills/using-superpowers/) | Use when starting any conversation - establishes how to find and use skills, requiring skill invocation before ANY response including clarifying questions |
| [`verification-before-completion`](skills/verification-before-completion/) | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always |
| [`writing-plans`](skills/writing-plans/) | Use when you have a spec or requirements for a multi-step task, before touching code |
| [`writing-skills`](skills/writing-skills/) | Use when creating new skills, editing existing skills, or verifying skills work before deployment |

### [officecli.ai](https://officecli.ai/SKILL.md)

| Skill | Use it when |
| --- | --- |
| [`officecli`](skills/officecli/) | Create, analyze, proofread, and modify Office documents (.docx, .xlsx, .pptx) using the officecli CLI tool. Use when the user wants to create, inspect, check formatting, find issues, add charts, or modify Office documents. |

### [paperclipai/paperclip](https://github.com/paperclipai/paperclip)

| Skill | Use it when |
| --- | --- |
| [`paperclip`](skills/paperclip/) | Interact with the Paperclip control plane API for task coordination and governance. Use when checking assignments, updating issue status, posting comments, delegating work, managing routines, or calling Paperclip API endpoints. |

### [TheQtCompanyRnD/agent-skills](https://github.com/TheQtCompanyRnD/agent-skills)

| Skill | Use it when |
| --- | --- |
| [`qt-qml`](skills/qt-qml/) | Applies QML best practices when producing or working with QML source code. Use whenever QML code is the primary subject: writing, reviewing, fixing, refactoring, optimizing, or debugging QML files, components, or bindings. Do NOT trigger for purely conversational QML questions where no code is produced or examined (e.g. "explain how anchors work"). |
| [`qt-qml-review`](skills/qt-qml-review/) | Invoke when the user asks to review, check, audit, or look over Qt6 QML code -- or suggest before committing. Runs deterministic linting (47+ rules) then six parallel deep- analysis agents covering bindings, layout, loaders, delegates, states, and performance. Optionally invokes system qmllint for type-level checks. Reports only high-confidence issues (>80/100) with structured mitigations. Read-only -- never modifies code. |

### [tt-a1i/archify](https://github.com/tt-a1i/archify)

| Skill | Use it when |
| --- | --- |
| [`archify`](skills/archify/) | Create polished, validated architecture, workflow, sequence, data-flow, and lifecycle/state diagrams as explorable standalone HTML with inline SVG, dark/light themes, optional trace motion, and PNG/JPEG/WebP/SVG/WebM export. Accept plain-language requirements or pasted Mermaid flowchart, sequenceDiagram, and stateDiagram input; inspect repository evidence when the diagram must reflect real code. Use when the user asks to visualize system architecture, infrastructure, cloud/security/network topology, technical workflows, API call sequences, request lifecycles, data pipelines, ETL/ELT, data lineage, state machines, or to convert/beautify Mermaid. |

<!-- skills:end -->

## Maintaining

```bash
bun run add obra/superpowers               # add every skill in a repo
bun run add Nutlope/hallmark -s hallmark   # or just the ones you name
bun run sync                               # refetch everything at latest upstream
bun run remove hallmark                    # drop one skill
bun run remove obra/superpowers            # drop every skill from that repo
```

All four rewrite the table above, so it can't drift; `git diff` shows what changed. `skills-lock.json` pins each skill's origin and content hash — commit it.

`design-taste` is a local super-skill amalgamating the 12 `Leonxlnx/taste-skill` skills (MIT, attributed per reference file). Do not re-add that repo — it would restore the 12 fragmented entries and their trigger collisions.

## Credit

Every skill here was written by someone else and is vendored unmodified under its own licence — see the Source column for where each came from. The tooling in `index.ts` is the only original work in this repo.

## Additional Resources

- [VoltAgent/awesome-agent-skills](https://raw.githubusercontent.com/VoltAgent/awesome-agent-skills/refs/heads/main/README.md) — A curated directory of official and community agent skills (including skills by Brave, VoltAgent, Supabase, Google, and more).

