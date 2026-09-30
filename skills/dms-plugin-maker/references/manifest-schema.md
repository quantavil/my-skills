# DMS Plugin Manifest (`plugin.json`) Specification

The manifest `plugin.json` resides at the root of every DankMaterialShell plugin. It is validated against the official DMS JSON schema on load.

---

## 1. Single-surface Manifest Example

```json
{
  "$schema": "https://danklinux.com/schemas/plugin.json",
  "id": "myPlugin",
  "name": "My Plugin Name",
  "description": "Short summary displayed in the DMS plugin browser",
  "version": "1.0.0",
  "author": "Author Name <author@example.com>",
  "type": "widget",
  "capabilities": ["dankbar-widget", "control-center"],
  "component": "./MyWidget.qml",
  "icon": "extension",
  "settings": "./MySettings.qml",
  "startupCheck": "./StartupCheck.qml",
  "requires_dms": ">=1.4.0",
  "dependencies": ["curl", "jq"],
  "permissions": [
    "settings_read",
    "settings_write",
    "process"
  ]
}
```

---

This example declares process permission for its external commands. Set the
minimum DMS version from the APIs actually used; the example version is not a
universal requirement. For composite plugins, use the components map for the
required surfaces rather than copying both entry-point forms indiscriminately.

## 2. Field Definitions & Constraints

| Field | Type | Required | Description & Constraints |
|---|---|---|---|
| `id` | `string` | **Yes** | Unique camelCase identifier matching `^[a-zA-Z][a-zA-Z0-9]*$`. Used for settings namespaces, translations, global variables, and bar configs. |
| `name` | `string` | **Yes** | Human-readable name displayed in DMS settings and bar widget selection menus. |
| `description` | `string` | **Yes** | 1-2 sentence description explaining the plugin's purpose. |
| `version` | `string` | **Yes** | Semantic version string (e.g. `"1.0.0"`). |
| `author` | `string` | **Yes** | Name or handle of the author. |
| `type` | `string` | **Yes** | Enum: `"widget"`, `"desktop"`, `"daemon"`, `"launcher"`, or `"composite"`. |
| `capabilities` | `array<string>` | **Yes** | Functional tags (e.g. `["dankbar-widget"]`, `["control-center"]`, `["desktop-widget"]`, `["daemon"]`, `["launcher"]`, `["monitoring"]`). |
| `component` | `string` | Single-surface | Path relative to root (e.g. `"./MyWidget.qml"`). Must match `^\./.*\.qml$`. |
| `components` | `object` | Composite | Map of surface target keys to QML paths: `"widget"`, `"desktop"`, `"daemon"`, `"launcher"`. |
| `trigger` | `string` | Launcher | Trigger prefix character for launcher search (e.g. `"#"`, `"="`). Use `""` for universal un-prefixed search. |
| `icon` | `string` | No | Material Symbols icon name (e.g. `"timer"`, `"schedule"`, `"cloud"`). |
| `settings` | `string` | No | Relative path to `PluginSettings` component (e.g. `"./MySettings.qml"`). |
| `startupCheck` | `string` | No | Relative path to a non-visual `QtObject` gating plugin activation. |
| `requires_dms` | `string` | No | Semver constraint against DMS shell version (e.g. `">=0.1.18"`, `">=1.6.0"`). |
| `dependencies` | `array<string>` | No | External CLI binaries required (e.g. `["curl", "grim", "pw-play"]`). |
| `permissions` | `array<string>` | No | Must include `["settings_read", "settings_write"]` if settings are saved. |

---

## 3. Surface Types Explained

1. **`widget`**:
   - Renders inside DankBar (top, bottom, left, or right).
   - Can optionally double as a Control Center tile with dropdown details.
   - Declares `horizontalBarPill`, `verticalBarPill`, and optional `popoutContent`.

2. **`desktop`**:
   - Renders directly on the desktop background layer (`WlrLayer.Bottom`).
   - Positioned, resized, and grid-snapped by DMS `DesktopPluginWrapper`.
   - Must use `DesktopPluginComponent` or standard `Item`.

3. **`daemon`**:
   - Headless background singleton.
   - Instantiated once on shell boot or plugin enablement.
   - Ideal for long-running watchers, D-Bus listeners, audio pipelines, and `IpcHandler` CLI servers.

4. **`launcher`**:
   - Integrates into the DMS Spotlight / Application Launcher.
   - Loaded lazily on the first time the launcher is opened.
   - Exposes `function getItems(query)` and `function executeItem(item)`.

5. **`composite`**:
   - Provides multiple surfaces simultaneously (e.g. a bar widget + background daemon + desktop widget).
   - Uses the `components` map. All surfaces share the same `pluginId` settings and global variables.

---

## 4. Startup Dependency Gate (`startupCheck`)

If your plugin requires system utilities or external daemons (e.g. `bluetoothctl`, `mpd`, `playerctl`), use `startupCheck` to prevent silent broken states.

Use the installed startup-check contract for `check(done)`. Use a supported
asynchronous Process API when exit status or output is required, then call done
with the framework's expected result. `Quickshell.execDetached([argv...])` does
not accept an exit/stdout callback; it only starts detached execution.

---

## 5. Schema validation

Use an actual JSON Schema validator with the installed or explicitly pinned DMS
schema. See [verification-and-testing.md](verification-and-testing.md). A script
that checks only required keys and settings permissions is a partial structural
check, not proof of schema conformance.
