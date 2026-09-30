---
name: dms-plugin-maker
description: >-
  Use when building, modifying, auditing, testing, or packaging DankMaterialShell
  plugins in Qt 6 QML and Quickshell: bar widgets, popouts, settings, daemons,
  desktop widgets, launchers, and Wayland overlays.
---

# DMS Plugin Maker

Build against the installed DMS runtime. Read its schema, Theme, PluginComponent,
PluginSettings, and PluginService before relying on remembered APIs. Runtime
sources may be under `/run/user/<uid>/danklinux-shell/<hash>/`; select the active
runtime rather than the first directory. These references describe observed
patterns, not a replacement for the current framework contract.

## Choose the references for the task

| Task | Read |
|---|---|
| Entry points, dependencies, permissions | [Manifest](references/manifest-schema.md) |
| Bar, popout, desktop, settings components | [Surfaces](references/surfaces-and-components.md) |
| Shared state, persistence, IPC, hydration | [State](references/state-and-persistence.md) |
| Scaling, typography, controls, duplicate settings | [Design](references/theme-and-styling.md) |
| Click dispatch, translations, focus, lifecycle | [Framework traps](references/framework-traps-and-gotchas.md) |
| Regression tests and live deployment | [Verification](references/verification-and-testing.md) |
| Registry contribution, overlap, ID migration, release | [Packaging](references/registry-and-release.md) |

## Architecture and ownership

For plugins with time calculations or substantial transitions, use a pure JS
engine, a reactive QML state bridge, and presentation components. Small plugins
can stay small; a separate engine, singleton, or IPC interface is not mandatory.

- Pass plain serializable snapshots to the engine, never QQuickItem objects.
- Keep effects (sounds, notifications, processes, persistence) at the bridge.
  Invoke processes asynchronously with argv arrays; detached execution does not
  provide a completion callback. Use a supported Process API when results matter.
- Share a singleton or framework global state across bars when sessions should
  synchronize. Register live instances and elect one effect/persistence owner;
  hand ownership over on destruction. `isFirst` describes bar position, not ownership.
- Hydrate without saving. Cache configured defaults separately from current
  session parameters. Settings reloads must preserve running, paused, and completed
  sessions; reset explicitly restores defaults. Account for synchronous signals.
- Define IPC start, restart, pause, reset, and dismissal semantics. Starting the
  same mode twice must follow that contract. Dismissing a ringing alarm must stop
  effects rather than schedule it again.

## QML invariants

- Preserve declarative bindings. Emit edits to the model; restore a TextInput's
  `text` binding with `Qt.binding(...)` after commit or cancel where needed.
- Guard global shortcuts while an editor has focus. Check the host's key routing
  contract; some popouts require `contentHandlesKeys` to deliver keys.
- Use Layout sizing for children managed by a Layout; avoid conflicting anchors.
  Derive auto-sized popout roots' `implicitHeight` from their content.
- Use unversioned Qt 6 imports. Keep singleton declarations consistent with qmldir.
- Use literal manifest IDs in `I18n.trFor`. Serialize colors to strings when saving.
- Request only permissions required by the current schema and invoked APIs.

## Design and verification decisions

Use actual Theme spacing, font, icon, and corner tokens, including custom controls
and fullscreen overlays. Derive larger readouts proportionally. Measure text and
controls together at increased font scale; scaling only the font clips controls.
Keep common alignment and spacing across modes while letting height fit content.
Do not impose fixed panel height just to make modes equal.

Give each editable preference one primary home. Put frequent session controls in
the popout and durable preferences in settings. Remove duplicate controls and
unsupported/dead options across UI, hydration, setters, and documentation. Preserve
legacy data safely. A timer's sound behavior is a product decision: define sensible
completion and dismissal behavior rather than adding a mute option by default.

When verification is requested or required for an authorized publication, select
checks appropriate to the plugin. Pure-engine tests, QML import lint, and actual
schema validation cover different failures; interactive state needs runtime QML
checks too. Live changes require task authorization, backups, and restoration of
preferences. Distinguish automated checks, observed live behavior, and untested
compatibility. See the verification reference for the regression matrix.
