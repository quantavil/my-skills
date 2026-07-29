# my-skills

A curated collection of agent skills. Each one is a real folder in `skills/` — read its `SKILL.md` directly, or install the lot:

```bash
bunx skills add quantavil/my-skills --all
```

## Skills

<!-- skills:start -->

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
| [`skill-creator`](skills/skill-creator/) | Create new skills, modify and improve existing skills, and measure skill performance. Use when users want to create a skill from scratch, edit, or optimize an existing skill, run evals to test a skill, benchmark skill performance with variance analysis, or optimize a skill's description for better triggering accuracy. |
| [`slack-gif-creator`](skills/slack-gif-creator/) | Knowledge and utilities for creating animated GIFs optimized for Slack. Provides constraints, validation tools, and animation concepts. Use when users request animated GIFs for Slack like "make me a GIF of X doing Y for Slack." |
| [`theme-factory`](skills/theme-factory/) | Toolkit for styling artifacts with a theme. These artifacts can be slides, docs, reportings, HTML landing pages, etc. There are 10 pre-set themes with colors/fonts that you can apply to any artifact that has been creating, or can generate a new theme on-the-fly. |
| [`web-artifacts-builder`](skills/web-artifacts-builder/) | Suite of tools for creating elaborate, multi-component claude.ai HTML artifacts using modern frontend web technologies (React, Tailwind CSS, shadcn/ui). Use for complex artifacts requiring state management, routing, or shadcn/ui components - not for simple single-file HTML/JSX artifacts. |
| [`webapp-testing`](skills/webapp-testing/) | Toolkit for interacting with and testing local web applications using Playwright. Supports verifying frontend functionality, debugging UI behavior, capturing browser screenshots, and viewing browser logs. |
| [`xlsx`](skills/xlsx/) | Use this skill any time a spreadsheet file is the primary input or output. This means any task where the user wants to: open, read, edit, or fix an existing .xlsx, .xlsm, .xltx, .csv, or .tsv file (e.g., adding columns, computing formulas, formatting, charting, cleaning messy data); create a new spreadsheet from scratch or from other data sources; or convert between tabular file formats. Trigger especially when the user references a spreadsheet file by name or path — even casually (like "the xlsx in my downloads") — and wants something done to it or produced from it. Also trigger for cleaning or restructuring messy tabular data files (malformed rows, misplaced headers, junk data) into proper spreadsheets. The deliverable must be a spreadsheet file. Do NOT trigger when the primary deliverable is a Word document, HTML report, standalone Python script, database pipeline, or Google Sheets API integration, even if tabular data is involved. |

### [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman)

| Skill | Use it when |
| --- | --- |
| [`cavecrew`](skills/cavecrew/) | Decision guide for delegating to caveman-style subagents. Tells the main thread WHEN to spawn `cavecrew-investigator` (locate code), `cavecrew-builder` (1-2 file edit), or `cavecrew-reviewer` (diff review) instead of doing the work inline or using vanilla `Explore`. Subagent output is caveman-compressed so the tool-result injected back into main context is ~60% smaller — main context lasts longer across long sessions. Trigger: "delegate to subagent", "use cavecrew", "spawn investigator/builder/reviewer", "save context", "compressed agent output". |
| [`caveman`](skills/caveman/) | Ultra-compressed communication mode. Cuts output tokens 65% (measured) by speaking like caveman while keeping full technical accuracy. Supports intensity levels: lite, full (default), ultra, wenyan-lite, wenyan-full, wenyan-ultra. Use when user says "caveman mode", "talk like caveman", "use caveman", "less tokens", "be brief", or invokes /caveman. Also auto-triggers when token efficiency is requested. |
| [`caveman-commit`](skills/caveman-commit/) | Ultra-compressed commit message generator. Cuts noise from commit messages while preserving intent and reasoning. Conventional Commits format. Subject ≤50 chars, body only when "why" isn't obvious. Use when user says "write a commit", "commit message", "generate commit", "/commit", or invokes /caveman-commit. Auto-triggers when staging changes. |
| [`caveman-compress`](skills/caveman-compress/) | Compress natural language memory files (CLAUDE.md, todos, preferences) into caveman format to save input tokens. Preserves all technical substance, code, URLs, and structure. Compressed version overwrites the original file. Human-readable backup saved as FILE.original.md. Trigger: /caveman-compress FILEPATH or "compress memory file" |
| [`caveman-help`](skills/caveman-help/) | Quick-reference card for all caveman modes, skills, and commands. One-shot display, not a persistent mode. Trigger: /caveman-help, "caveman help", "what caveman commands", "how do I use caveman". |
| [`caveman-review`](skills/caveman-review/) | Ultra-compressed code review comments. Cuts noise from PR feedback while preserving the actionable signal. Each comment is one line: location, problem, fix. Use when user says "review this PR", "code review", "review the diff", "/review", or invokes /caveman-review. Auto-triggers when reviewing pull requests. |

### [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)

| Skill | Use it when |
| --- | --- |
| [`brandkit`](skills/brandkit/) | Premium brand-kit image generation skill for creating high-end brand-guidelines boards, logo systems, identity decks, and visual-world presentations. Trained for minimalist, cinematic, editorial, dark-tech, luxury, cultural, security, gaming, developer-tool, and consumer-app brand systems. Optimized for intentional logo concepting, refined composition, sparse typography, strong symbolic meaning, premium mockups, art-directed imagery, and flexible grid layouts. |
| [`design-taste-frontend`](skills/design-taste-frontend/) | Anti-slop frontend skill for landing pages, portfolios, and redesigns. The agent reads the brief, infers the right design direction, and ships interfaces that do not look templated. Real design systems when applicable, audit-first on redesigns, strict pre-flight check. |
| [`design-taste-frontend-v1`](skills/design-taste-frontend-v1/) | The original v1 taste-skill, preserved for projects depending on its exact behavior. The current default is `design-taste-frontend` (v2 experimental), which is a substantial rewrite. Use this v1 install name only if you need exact backward compatibility. |
| [`full-output-enforcement`](skills/full-output-enforcement/) | Overrides default LLM truncation behavior. Enforces complete code generation, bans placeholder patterns, and handles token-limit splits cleanly. Apply to any task requiring exhaustive, unabridged output. |
| [`gpt-taste`](skills/gpt-taste/) | Elite UX/UI & Advanced GSAP Motion Engineer. Enforces Python-driven true randomization for layout variance, strict AIDA page structure, wide editorial typography (bans 6-line wraps), gapless bento grids, strict GSAP ScrollTriggers (pinning, stacking, scrubbing), inline micro-images, and massive section spacing. |
| [`high-end-visual-design`](skills/high-end-visual-design/) | Teaches the AI to design like a high-end agency. Defines the exact fonts, spacing, shadows, card structures, and animations that make a website feel expensive. Blocks all the common defaults that make AI designs look cheap or generic. |
| [`image-to-code`](skills/image-to-code/) | Elite website image-to-code skill for Codex. For visually important web tasks, it must first generate the design image(s) itself, deeply analyze them, then implement the website to match them as closely as possible. In Codex, it must prefer large, readable, section-specific images instead of tiny compressed boards, generate fresh standalone images for sections or detail views instead of cropping old ones, avoid lazy under-generation, avoid cards-inside-cards-inside-cards UI, and keep the hero clean, spacious, readable, and visible on a small laptop. |
| [`imagegen-frontend-mobile`](skills/imagegen-frontend-mobile/) | Elite mobile app image-generation skill for creating premium, app-native screen concepts and flows. Designed for iOS, Android, and cross-platform mobile products. Prioritizes clean hierarchy, comfortably readable text, strong multi-screen consistency, controlled color palettes, non-generic creative direction, textured surfaces, image-led composition, tasteful custom iconography, and clean phone mockup framing. By default, screens should be shown inside a subtle premium iPhone or similar phone mockup with a visible frame, while the main focus stays on the app content itself. This skill generates images only. It does not write code. |
| [`imagegen-frontend-web`](skills/imagegen-frontend-web/) | Elite frontend image-direction skill for generating premium, conversion-aware website design references. CRITICAL OUTPUT RULE — generate ONE separate horizontal image FOR EVERY section. A landing page with 8 sections produces 8 images. Never compress multiple sections into one image. Enforces composition variety (not always left-text / right-image), background-image freedom, varied CTAs, varied hero scales (giant / mid / mini minimalist), narrative concept spine, second-read moments, and a single consistent palette across all images. Optimized for landing pages, marketing sites, and product comps that developers or coding models can accurately recreate. |
| [`industrial-brutalist-ui`](skills/industrial-brutalist-ui/) | Raw mechanical interfaces fusing Swiss typographic print with military terminal aesthetics. Rigid grids, extreme type scale contrast, utilitarian color, analog degradation effects. For data-heavy dashboards, portfolios, or editorial sites that need to feel like declassified blueprints. |
| [`minimalist-ui`](skills/minimalist-ui/) | Clean editorial-style interfaces. Warm monochrome palette, typographic contrast, flat bento grids, muted pastels. No gradients, no heavy shadows. |
| [`redesign-existing-projects`](skills/redesign-existing-projects/) | Upgrades existing websites and apps to premium quality. Audits current design, identifies generic AI patterns, and applies high-end design standards without breaking functionality. Works with any CSS framework or vanilla CSS. |
| [`stitch-design-taste`](skills/stitch-design-taste/) | Semantic Design System Skill for Google Stitch. Generates agent-friendly DESIGN.md files that enforce premium, anti-generic UI standards — strict typography, calibrated color, asymmetric layouts, perpetual micro-motion, and hardware-accelerated performance. |

### [Nutlope/hallmark](https://github.com/Nutlope/hallmark)

| Skill | Use it when |
| --- | --- |
| [`hallmark`](skills/hallmark/) | Anti-AI-slop design skill for greenfield pages, audits, redesigns, and design extraction from URLs or screenshots. Use when the user asks to build a new app or landing page, wants to redesign something, invokes Hallmark by name, or uses audit/redesign/study. |

### [obra/superpowers](https://github.com/obra/superpowers)

| Skill | Use it when |
| --- | --- |
| [`brainstorming`](skills/brainstorming/) | You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation. |
| [`dispatching-parallel-agents`](skills/dispatching-parallel-agents/) | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies |
| [`executing-plans`](skills/executing-plans/) | Use when you have a written implementation plan to execute in a separate session with review checkpoints |
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

## Credit

Every skill here was written by someone else and is vendored unmodified under its own licence — see the Source column for where each came from. The tooling in `index.ts` is the only original work in this repo.
