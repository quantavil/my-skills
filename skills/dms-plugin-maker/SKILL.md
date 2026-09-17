---
name: dms-plugin-maker
description: >-
  Architect, build, audit, test, and package production-ready plugins for DankMaterialShell (DMS) and Quickshell on Linux Wayland.
  Use whenever developing, modifying, reviewing, or testing DMS bar widgets, popout panels, desktop widgets, daemons,
  launchers, settings pages, or Wayland overlays. Enforces Qt 6 QML declarative binding hygiene, pure-JS calculation engine architecture,
  DMS Material 3 theme tokens, multi-monitor instance safety, and the triple-validation testing rig.
---

# DankMaterialShell (DMS) Plugin Maker

DankMaterialShell (DMS) is a modern Material 3 desktop shell for Wayland compositors (Hyprland, Niri, Sway) built on top of **Quickshell** and **Qt 6 / QML**.

This skill codifies the official DMS plugin specifications, architectural patterns, design system tokens, and verification checklists derived from DMS core runtime analysis and production plugins.

---

## 📚 Quick Navigation & Reference Guides

Detailed reference specifications are bundled in `references/`:

| Topic | Reference Document | What It Covers |
|---|---|---|
| **Manifest & Schema** | [`references/manifest-schema.md`](references/manifest-schema.md) | `plugin.json` keys, surface enums, startup gates (`startupCheck`), and permissions. |
| **Surfaces & Components** | [`references/surfaces-and-components.md`](references/surfaces-and-components.md) | `PluginComponent` (bars/CC), `DesktopPluginComponent`, `Daemon`, `Launcher`, and all 7 Settings components. |
| **State & Persistence** | [`references/state-and-persistence.md`](references/state-and-persistence.md) | The 4 data storage channels (`pluginData`, `pluginState`, `PluginGlobalVar`, `IpcHandler`) and the Variants system. |
| **Theme & Styling** | [`references/theme-and-styling.md`](references/theme-and-styling.md) | Material 3 color roles, typography metrics, spacing scale, corner radii, and theme snapping utilities. |
| **Traps & Gotchas** | [`references/framework-traps-and-gotchas.md`](references/framework-traps-and-gotchas.md) | Top 12 real-world framework quirks: arity dispatch, popout collapsing, clipboard traps, and Fitts's law margins. |
| **Testing & Verification** | [`references/verification-and-testing.md`](references/verification-and-testing.md) | The Triple-Validation Suite: Node.js engine unit tests, `qmllint` syntax validation, and manifest schema testing. |

---

## 1. Core Architecture: The 3-Tier Pattern

Every robust DMS plugin must enforce a clean separation of concerns:

```
my-dms-plugin/
├── plugin.json               # Manifest metadata and capabilities
├── qmldir                    # QML module export (declares components & singletons)
├── MyWidget.qml              # Bar widget (PluginComponent, horizontal/vertical pills, popout)
├── MyPopout.qml              # Popout panel (PopoutComponent, interactive controls)
├── MySettings.qml            # Declarative PluginSettings page in DMS settings window
├── MyState.qml               # QML singleton bridge: timers, IPC, non-blocking processes
├── MyEngine.js               # Pure JS calculation engine (100% testable, zero UI deps)
└── tests/
    ├── test_engine.js        # Node.js pure engine unit tests
    ├── test_qml_syntax.sh    # qmllint syntax validator
    └── validate_manifest.py  # JSON Schema validator for plugin.json
```

### Layer Responsibilities

1. **Pure Calculation Engine (`*Engine.js`)**:
   - Stateless or pure state-transition functions: `tick(state, nowMs) -> { state, events }`.
   - Never import QML, Quickshell, or UI modules.
   - Zero DOM, window, or file I/O references.
   - 100% unit-testable directly with `node tests/test_engine.js` without a display server.

2. **Reactive State Bridge Singleton (`*State.qml`)**:
   - Declared as a QML singleton in `qmldir` (`singleton MyPluginState 1.0 MyState.qml`).
   - Single source of truth for runtime properties (`running`, `displayText`, `progress`).
   - Runs background `Timer` objects (adaptive tick intervals: fast when visible, slow/idle when hidden).
   - Hosts `IpcHandler` for CLI commands (`dms ipc call <id> <method>`).
   - Bridges to non-blocking system processes via `Quickshell.execDetached`.

3. **UI Presentation (`*Widget.qml`, `*Popout.qml`, `*Settings.qml`)**:
   - Purely reactive bindings reading from `State.qml`.
   - Never perform time math, interval arithmetic, or complex state transitions inside QML expressions.
   - Calls explicit mutator functions on `State.qml`.

---

## 2. Manifest Quick-Matrix (`plugin.json`)

The manifest defines the entry points and capabilities.

| Plugin Surface | Manifest Type | Target Key | Base QML Component |
|---|---|---|---|
| **Bar / CC Widget** | `"widget"` | `component: "./Widget.qml"` | `PluginComponent` |
| **Desktop Widget** | `"desktop"` | `component: "./Desktop.qml"` | `DesktopPluginComponent` |
| **Daemon** | `"daemon"` | `component: "./Daemon.qml"` | `Item` or `QtObject` |
| **Launcher** | `"launcher"` | `component: "./Launcher.qml"` | `Item` (exposes `getItems`, `executeItem`) |
| **Composite** | `"composite"` | `components: { widget, desktop, daemon, launcher }` | Subset of above |

> [!IMPORTANT]
> If your plugin includes a `settings` component, your manifest **MUST** declare:
> `"permissions": ["settings_read", "settings_write"]`
> Omitting `"settings_write"` causes `PluginSettings` to block user saves and display an access error banner.

---

## 3. Critical QML Binding Hygiene & Memory Rules

AI models frequently treat QML like JavaScript or React, introducing subtle bugs. Adhere strictly to these rules:

### Rule 1: Declarative Binding Preservation
* **The Antipattern:** Imperatively assigning to a property (`editor.text = "05"`) destroys the QML reactive binding permanently.
* **The Rule:** In steppers and buttons, do **not** assign directly to visual child text. Emit a signal `modified(newVal)` that updates the parent property, letting the declarative binding (`text: Engine.pad2(root.value)`) update reactively.
* If a user types directly into a `TextInput`, Qt inherently unbinds `text`. Always re-establish the binding on edit commit or escape:
  ```qml
  editor.text = Qt.binding(() => Engine.pad2(root.value));
  ```

### Rule 2: Never Pass `QQuickItem` into Pure JS Engines
* **The Antipattern:** Passing `root` (a `QQuickItem`) to pure JS engine functions causes `Object.assign({}, state)` to clone 90+ internal QtQuick properties on every frame/tick, introducing massive garbage collection churn and latency spikes.
* **The Rule:** Implement a clean snapshot helper on the state item that packages only primitive/serializable fields:
  ```qml
  function getEngineSnapshot() {
      return {
          mode: root.mode,
          running: root.running,
          elapsedMs: root.elapsedMs,
          durationMs: root.durationMs
      };
  }
  // Call engine with pure JS object
  var res = Engine.tick(root.getEngineSnapshot(), Date.now());
  ```

### Rule 3: Layouts vs. Anchors
* **Never mix `anchors.*` and `Layout.*` on the same item.**
* Inside `RowLayout`, `ColumnLayout`, or `GridLayout`:
  - Size items using `Layout.preferredWidth`, `Layout.fillWidth: true`, `Layout.preferredHeight`.
  - **Never** set hardcoded `width` or `height` directly on children of a Layout.
* Use lightweight `Row` or `Column` with `spacing` for static positioning; use `RowLayout` / `ColumnLayout` only when responsive resizing/expansion is needed.

### Rule 4: No Versioned Imports in Qt 6
* Write `import QtQuick`, `import Quickshell`, `import qs.Common`.
* Never append legacy Qt 5 versions like `import QtQuick 2.15`.

---

## 4. State Storage Decision Tree

DMS provides four distinct data channels:

```
Do you need to store data?
├── Is it persistent across reboots?
│   ├── Is it user configuration/options? ─────────► Channel 1: pluginData / PluginSettings
│   │                                               (Saved to ~/.config/DankMaterialShell/settings.json)
│   └── Is it application data, notes, or cache? ─► Channel 2: pluginState API
│                                                   (Saved to ~/.local/state/quickshell/dms/plugins/<id>_state.json)
└── Is it runtime/session state?
    ├── Must it synchronize across multiple bars? ─► Channel 3: PluginGlobalVar / PluginService
    │                                               (Reactive in-memory RAM sync across monitors)
    └── Is it for CLI or foreign scripts? ─────────► Channel 4: IpcHandler
                                                    (Invoked via: dms ipc call <id> <method>)
```

### The Multi-Instance Startup Hydration Rule
On multi-monitor setups, DMS instantiates `Widget.qml` once per monitor. If the widget's startup hydration emits `settingSaveRequested`, all instances concurrently re-save the loaded settings to disk on boot.
* **Always** accept an optional `notifyHost` flag in state setters:
  ```qml
  function setDuration(value, notifyHost) {
      var v = Math.max(1, Number(value) || 1);
      if (root.duration === v) return;
      root.duration = v;
      if (notifyHost === undefined || notifyHost) {
          root.settingSaveRequested("duration", v);
      }
  }
  ```
* Pass `false` during startup hydration in `Widget.qml` and `Settings.qml`.

---

## 5. DMS Material 3 Design System Quick Reference

Import `qs.Common` and `qs.Widgets` for native styling:

### Theme Tokens (`Theme.*`)
- **Colors**: `Theme.primary`, `Theme.primaryText`, `Theme.surfaceText`, `Theme.surfaceVariantText`, `Theme.surfaceContainerHigh`, `Theme.surfaceContainer`, `Theme.error`, `Theme.outlineVariant`.
- **Metrics**: `Theme.cornerRadius` (default 12), `Theme.spacingXS` (4), `Theme.spacingS` (8), `Theme.spacingM` (12), `Theme.spacingL` (16).
- **Typography**: `Theme.fontSizeSmall` (12), `Theme.fontSizeMedium` (14), `Theme.fontSizeLarge` (16), `Theme.fontFamily`, `Theme.monoFontFamily`.
- **Icons**: `Theme.iconSize` (24), `Theme.iconSizeSmall` (16).
- **Bar Helpers**: `root.iconSize`, `root.iconSizeLarge` (automatically scaled to bar thickness).

### Standard Visual Primitives
- **`StyledRect`**: Rounded background container:
  ```qml
  StyledRect {
      color: Theme.surfaceContainerHigh
      radius: Theme.cornerRadius
  }
  ```
- **`StyledText`**: Text label supporting theme colors and localization:
  ```qml
  StyledText {
      text: I18n.trFor("myPlugin", "Active Session")
      font.pixelSize: Theme.fontSizeMedium
      color: Theme.surfaceText
  }
  ```
- **`DankIcon`**: Material Symbols icon:
  ```qml
  DankIcon {
      name: "timer"
      size: root.iconSize
      color: Theme.primary
  }
  ```

---

## 6. Framework Red Flags & Traps Checklist

Before finalizing any plugin, check against these 8 critical failure modes:

| Check | Red Flag | Correct Implementation |
|---|---|---|
| **Clipboard** | ❌ `navigator.clipboard.writeText(...)` | ✅ `Quickshell.execDetached(["dms", "cl", "copy", text])` |
| **Popout Height** | ❌ `popoutHeight: 0` with no child `implicitHeight` (collapses to 16px) | ✅ Set `implicitHeight: col.implicitHeight` on popout root child |
| **Color Save** | ❌ `savePluginData("color", myColor)` (writes `{}`) | ✅ `savePluginData("color", myColor.toString())` (saves hex string) |
| **Click Arity** | ❌ `pillClickAction: (x = 0, y = 0) => ...` (JS sets length to 0!) | ✅ `pillClickAction: (x, y, width, section, screen) => ...` (no defaults) |
| **Translations** | ❌ `I18n.trFor(pluginId, "Text")` (variable arg fails AST extraction) | ✅ `I18n.trFor("myPlugin", "Text")` (exact literal string) |
| **Startup Gate** | ❌ `Item` or visual component in `startupCheck` | ✅ Non-visual `QtObject` with `function check(done)` |
| **Process Exec** | ❌ Synchronous shell commands or blocking loops | ✅ `Quickshell.execDetached(["cmd", "arg"])` or `Proc.runCommand(...)` |
| **Desktop Focus**| ❌ Text input in desktop widget won't accept typing | ✅ Declare `property bool acceptsKeyboardFocus: true` |

---

## 7. The Triple-Validation Verification Rig

Run this multi-phase verification harness before publishing any DMS plugin:

```bash
# Phase 1: Pure JS Engine Unit Tests
node tests/test_engine.js

# Phase 2: QML Syntax & Module Linting
bash tests/test_qml_syntax.sh
# or directly:
qmllint *.qml

# Phase 3: Manifest Schema Compliance
python3 tests/validate_manifest.py

# Phase 4: Live DMS Deployment & Verification
ln -sf "$PWD" ~/.config/DankMaterialShell/plugins/<myPluginId>
dms restart
dms ipc call <myPluginId> status
```
