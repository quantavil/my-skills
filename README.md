# my-skills

A curated collection of agent skills. Each one is a real folder in `skills/` — read its `SKILL.md` directly, or install the lot:

```bash
bunx skills add quantavil/my-skills --all
```

Ditto is maintained in this repository. Install it alone with `bunx skills add quantavil/my-skills --skill ditto`. Its evidence workflow covers Android/iOS inspection, Flutter reconstruction, and differential validation. Local skills are excluded from upstream sync.

## Skills

<!-- skills:start -->

### [./skills/ditto](https://github.com/quantavil/my-skills/tree/main/skills/ditto)

| Skill | Use it when |
| --- | --- |
| [`ditto`](skills/ditto/) | Reconstruct an existing Android or iOS app in Flutter using an APK, IPA, app bundle, or running app as evidence. Use for mobile app replication, binary-to-Flutter migration, behavioral specification extraction, and differential parity testing. Does not recover original source or apply to generic Flutter development or the Ditto clipboard app. |

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

### [blader/humanizer](https://github.com/blader/humanizer)

| Skill | Use it when |
| --- | --- |
| [`humanizer`](skills/humanizer/) | Rewrite AI-sounding text so it reads like the writer without changing what it says. Use when editing or reviewing prose for AI tells: not-X-but-Y contrasts, one-line closers, staged openers, forced triads, dashes everywhere, inflated claims, sales language, stock AI words, bold labels, or filler. Based on Wikipedia's "Signs of AI writing." |

### [HKUDS/DeepTutor](https://raw.githubusercontent.com/HKUDS/DeepTutor/main/SKILL.md)

| Skill | Use it when |
| --- | --- |
| [`deeptutor-cli`](skills/deeptutor-cli/) | Configure, manage, and use DeepTutor through its CLI, including capabilities, knowledge bases, partners, memory, sessions, notebooks, providers, skills, and the server or Web app. |

### [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman)

| Skill | Use it when |
| --- | --- |
| [`cavecrew`](skills/cavecrew/) | When to delegate to `cavecrew-investigator` (locate code), `cavecrew-builder` (1-2 file edit) or `cavecrew-reviewer` (diff review) instead of working inline or using `Explore`. Their output is compressed, so main context lasts longer. |
| [`caveman`](skills/caveman/) | Ultra-compressed communication mode that cuts output tokens while keeping technical accuracy. Levels: lite, full, ultra and the wenyan variants. Use for /caveman, "caveman mode", "talk like caveman", "be brief" or "less tokens". |
| [`caveman-commit`](skills/caveman-commit/) | Write a Conventional Commits message compressed to intent only. Use for "write a commit", "commit message", /commit or /caveman-commit. |
| [`caveman-compress`](skills/caveman-compress/) | Compress a memory file such as CLAUDE.md or a todo list into caveman format to save input tokens, keeping a readable backup. Trigger: /caveman-compress. |
| [`caveman-help`](skills/caveman-help/) | Quick-reference card for caveman modes, skills and commands. Trigger: /caveman-help or "caveman help". |
| [`caveman-review`](skills/caveman-review/) | Compressed code review - one line per finding with location, problem and fix. Use for /caveman-review, "review this PR", or "review the diff". |

### [karanb192/itr-wala](https://github.com/karanb192/itr-wala)

| Skill | Use it when |
| --- | --- |
| [`itr-wala`](skills/itr-wala/) | File Indian income tax returns (ITR) for FY 2025-26 / AY 2026-27. Use when the user wants to file their ITR, compute or verify Indian income tax, compare the old vs new tax regime, read a Form 16, AIS, TIS or Form 26AS, reconcile TDS, handle capital gains from Zerodha/Groww/Upstox statements, check their tax refund, or asks about ITR-1/ITR-2/ITR-3/ITR-4, sections 80C/80D/87A/111A/112A, crypto tax, advance tax, or the income-tax e-filing portal - even if they just say "help me with my taxes" in an Indian context. |

### [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)

| Skill | Use it when |
| --- | --- |
| [`brandkit`](skills/brandkit/) | Premium brand-kit image generation skill for creating high-end brand-guidelines boards, logo systems, identity decks, and visual-world presentations. Trained for minimalist, cinematic, editorial, dark-tech, luxury, cultural, security, gaming, developer-tool, and consumer-app brand systems. Optimized for intentional logo concepting, refined composition, sparse typography, strong symbolic meaning, premium mockups, art-directed imagery, and flexible grid layouts. |
| [`design-taste-frontend`](skills/design-taste-frontend/) | Anti-slop frontend skill for landing pages, portfolios, and redesigns. The agent reads the brief, infers the right design direction, and ships interfaces that do not look templated. Real design systems when applicable, audit-first on redesigns, strict pre-flight check. |
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

### [officecli.ai](https://officecli.ai/SKILL.md)

| Skill | Use it when |
| --- | --- |
| [`officecli`](skills/officecli/) | Create, analyze, proofread, and modify Office documents (.docx, .xlsx, .pptx) using the officecli CLI tool. Use when the user wants to create, inspect, check formatting, find issues, add charts, or modify Office documents. |

### [tt-a1i/archify](https://github.com/tt-a1i/archify)

| Skill | Use it when |
| --- | --- |
| [`archify`](skills/archify/) | Create polished, validated architecture, workflow, sequence, data-flow, and lifecycle/state diagrams as explorable standalone HTML with inline SVG, dark/light themes, optional trace motion, and PNG/JPEG/WebP/SVG/WebM export. Accept plain-language requirements or pasted Mermaid flowchart, sequenceDiagram, and stateDiagram input; inspect repository evidence when the diagram must reflect real code. Use when the user asks to visualize system architecture, infrastructure, cloud/security/network topology, technical workflows, API call sequences, request lifecycles, data pipelines, ETL/ELT, data lineage, state machines, or to convert/beautify Mermaid. |

### [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills)

| Skill | Use it when |
| --- | --- |
| [`deploy-to-vercel`](skills/deploy-to-vercel/) | Deploy applications and websites to Vercel. Use when the user requests deployment actions like "deploy my app", "deploy and give me the link", "push this live", or "create a preview deployment". |
| [`vercel-cli-with-tokens`](skills/vercel-cli-with-tokens/) | Deploy and manage projects on Vercel using token-based authentication. Use when working with Vercel CLI using access tokens rather than interactive login — e.g. "deploy to vercel", "set up vercel", "add environment variables to vercel". |
| [`vercel-composition-patterns`](skills/vercel-composition-patterns/) | React composition patterns that scale. Use when refactoring components with boolean prop proliferation, building flexible component libraries, or designing reusable APIs. Triggers on tasks involving compound components, render props, context providers, or component architecture. Includes React 19 API changes. |
| [`vercel-optimize`](skills/vercel-optimize/) | Use for Vercel cost and performance optimization on deployed projects, especially Next.js, SvelteKit, Nuxt, and limited Astro apps. Collect Vercel metrics, usage, project config, and code scan results first; investigate only metric-backed candidates; produce ranked recommendations grounded in verified files and version-aware Vercel/framework docs. Trigger for Vercel bill reduction, slow or expensive routes, caching opportunities, Function Invocations, Build Minutes, Fast Data Transfer, Core Web Vitals, Bot Management, Fluid compute, or cost breakdown requests. |
| [`vercel-react-best-practices`](skills/vercel-react-best-practices/) | React and Next.js performance optimization guidelines from Vercel Engineering. This skill should be used when writing, reviewing, or refactoring React/Next.js code to ensure optimal performance patterns. Triggers on tasks involving React components, Next.js pages, data fetching, bundle optimization, or performance improvements. |
| [`vercel-react-native-skills`](skills/vercel-react-native-skills/) | React Native and Expo best practices for building performant mobile apps. Use when building React Native components, optimizing list performance, implementing animations, or working with native modules. Triggers on tasks involving React Native, Expo, mobile performance, or native platform APIs. |
| [`vercel-react-view-transitions`](skills/vercel-react-view-transitions/) | Guide for implementing smooth, native-feeling animations using React's View Transition API (`<ViewTransition>` component, `addTransitionType`, and CSS view transition pseudo-elements). Use this skill whenever the user wants to add page transitions, animate route changes, create shared element animations, animate enter/exit of components, animate list reorder, implement directional (forward/back) navigation animations, or integrate view transitions in Next.js. Also use when the user mentions view transitions, `startViewTransition`, `ViewTransition`, transition types, or asks about animating between UI states in React without third-party animation libraries. |
| [`web-design-guidelines`](skills/web-design-guidelines/) | Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices". |
| [`writing-guidelines`](skills/writing-guidelines/) | Review docs/prose for Writing Guidelines compliance. Use when asked to "review my docs", "check writing style", "audit prose", "review docs voice and tone", or "check this page against the writing handbook". |

### Unsourced

| Skill | Use it when |
| --- | --- |
| [`flutter-dart`](skills/flutter-dart/) | Master skill for Dart and Flutter development. Covers architecture best practices, UI and responsive layouts, layout debugging (RenderFlex overflow), declarative routing (go_router), localization (l10n/i18n), REST API integration (http), JSON serialization, unit/widget/integration testing (package:test, WidgetTester, package:checks, mockito), static analysis, runtime error debugging, FFI and native assets (ffigen, hooks), CLI apps, and documentation. |
| [`gstr-wala`](skills/gstr-wala/) | File Indian Goods and Services Tax (GST) returns for regular taxpayers, including GSTR-1 (outward supplies), GSTR-3B (monthly summary return), GSTR-2B reconciliation, and PDF invoice vision extraction. Use when the user wants to file GSTR-1 or GSTR-3B, reconcile purchase registers against GSTR-2B, optimize ITC set-off under Rule 88A / Section 49, compute Section 50 interest or Section 47 late fees, check DRC-01B / DRC-01C mismatch risks, convert multi-page PDF/image bills to page-by-page visual images, generate official GST portal offline JSON returns, render certified CA tax audit statements, check live statutory compliance updates, or asks about GST rates, HSN codes, Table 4 ITC, blocked credit under Section 17(5), or PMT-06 challan generation. |
| [`orchestrator`](skills/orchestrator/) | Use when delegating bounded, verifiable coding work to a CLI model, then verifying and auditing the result before accepting it. |

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

## Additional Resources

- [VoltAgent/awesome-agent-skills](https://raw.githubusercontent.com/VoltAgent/awesome-agent-skills/refs/heads/main/README.md) — A curated directory of official and community agent skills (including skills by Brave, VoltAgent, Supabase, Google, and more).

