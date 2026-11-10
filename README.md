# my-skills

One skill library for every local AI agent. Everything is a **bundle**: a whole upstream repo (all its skills, never a subset) or one of your own skills in `skills/`. `deploy` symlinks bundles into each agent's skills folder and leaves links it doesn't own alone.

```bash
./run.sh sync              # download every upstream bundle (latest default branch), then build
./run.sh deploy            # build, then link into the targets in bundles.json
./run.sh deploy --dry-run  # show what would change
./run.sh check             # bundles.json valid, vendor/ complete, build and README current
./run.sh list
bun run test && bun run typecheck
```

To add, remove or retier a bundle, edit `bundles.json`, then run `sync` (for a new upstream repo) or `deploy`.

## Bundles

<!-- bundles:start -->

| Bundle | Tier | Skills | Source | Use for |
| --- | --- | --- | --- | --- |
| `agent-browser` | core | 10 | [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) | browser automation with the agent-browser CLI: open sites, fill forms, click, screenshot, scrape, test web apps, and drive Electron apps, Slack and cloud browsers |
| `humanizer` | core | 1 | [blader/humanizer](https://github.com/blader/humanizer) | rewriting AI-sounding prose |
| `i-have-adhd` | core | 1 | [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd) | ADHD-friendly output mode (/i-have-adhd) |
| `superpowers` | core | 15 | [obra/superpowers](https://github.com/obra/superpowers) | software development: planning features, implementing changes, debugging failures, reviewing code, testing, and finishing branches |
| `visual-explainer` | core | 1 | [nicobailon/visual-explainer](https://github.com/nicobailon/visual-explainer) | HTML visual explanations: diagrams, diff and plan reviews, slides, recaps |
| `android-skills` | gateway | 36 | [android/skills](https://github.com/android/skills) | Android app development: Jetpack Compose, navigation, AGP 9 and Play Billing upgrades, Wear OS, TV, XR, Glance widgets, performance and ANR fixes, R8, and Android security |
| `anthropic` | gateway | 20 | [anthropics/skills](https://github.com/anthropics/skills) | Office files (Word, Excel, PowerPoint, PDF), MCP servers, Claude API, generative art |
| `caveman` | gateway | 22 | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | terse caveman-style replies, commits and reviews |
| `design-taste-frontend` | gateway | 1 | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | frontend design with taste (anti-slop websites) |
| `ditto` | gateway | 1 | local | cloning an Android app by reverse engineering |
| `dms-plugin-maker` | gateway | 1 | local | DankMaterialShell (DMS) plugins |
| `engram` | gateway | 3 | [nagisanzenin/engram](https://github.com/nagisanzenin/engram) | learning a topic, spaced-repetition reviews |
| `fact-check` | gateway | 1 | local | fact-checking a video, audio or transcript |
| `gstr-wala` | gateway | 1 | [quantavil/gstr-wala](https://github.com/quantavil/gstr-wala) | Indian GST returns (GSTR-1, 3B, 2B) |
| `gws` | gateway | 95 | [googleworkspace/cli](https://github.com/googleworkspace/cli) | Google Workspace CLI: Gmail, Drive, Sheets, Calendar, Docs |
| `itr-wala` | gateway | 1 | [karanb192/itr-wala](https://github.com/karanb192/itr-wala) | Indian income tax returns (ITR) |
| `myanimelist` | gateway | 1 | local | MyAnimeList lists and anime recommendations |
| `qt` | gateway | 13 | [TheQtCompanyRnD/agent-skills](https://github.com/TheQtCompanyRnD/agent-skills) | Qt 6 QML and C++: write, review, test, profile |

<!-- bundles:end -->

## How it works

- **`bundles.json`** (committed) lists each bundle with a `tier`, a `summary`, and a `repo` (`owner/repo`, a git URL or a path). A bundle with no `repo` is local, in `skills/<name>/`. `targets` lists the agents to deploy to.
- **`sync`** shallow-clones each repo and copies every folder that has a `SKILL.md` into `vendor/<bundle>/`. If a repo mirrors a skill in two places, the shallowest copy wins. A repo whose root is a skill is copied whole. Skills with unparseable frontmatter are skipped with a warning. Each sync replaces the folder, so never edit `vendor/`; make a local skill instead.
- **Build** (`./run.sh`, run by `sync` and `deploy`):
  - **One-skill bundles** are linked as they are, and the bundle name must match the skill's `name`.
  - **Multi-skill bundles** get a router `SKILL.md` in `.build/<bundle>/`, described as "Use for <summary>", with a table of guides. The member skills are copied beside it with `SKILL.md` renamed to `GUIDE.md`, so agents only discover the router and read just the guide a task needs.
- **Tiers**:
  - **core**: linked into every agent.
  - **gateway**: not linked. The generated `find-skill` router lists them instead. Its description joins their summaries, so it triggers on those topics, and its table gives the path to each one's entry file. Gateway skills can't be run as `/name` commands, so keep user-invoked ones in core.

`vendor/` and `.build/` are per-machine output, ignored by git. Run `./run.sh sync && ./run.sh deploy` after cloning and whenever you want the latest upstream. Some skills need their own runtime: for example, visual-explainer's video export needs `npm install` in `vendor/visual-explainer/visual-explainer`, and Engram needs an [Engram checkout](https://github.com/nagisanzenin/engram).
