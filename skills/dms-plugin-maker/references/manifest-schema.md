# DMS Plugin Manifest (`plugin.json`) Specification

The manifest `plugin.json` resides at the root of every DankMaterialShell plugin. It is validated against the official DMS JSON schema on load.

---

## 1. Complete Manifest Reference

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
  "components": {
    "widget": "./MyWidget.qml",
    "desktop": "./MyDesktopWidget.qml",
    "daemon": "./MyDaemon.qml",
    "launcher": "./MyLauncher.qml"
  },
  "trigger": "#",
  "icon": "extension",
  "settings": "./MySettings.qml",
  "startupCheck": "./StartupCheck.qml",
  "requires_dms": ">=0.1.18",
  "dependencies": ["curl", "jq"],
  "permissions": [
    "settings_read",
    "settings_write"
  ]
}
```

---

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

```qml
// StartupCheck.qml - MUST be a QtObject (NEVER an Item)
import QtQuick
import Quickshell

QtObject {
    // Asynchronous check: done(null) for success; done(error) for failure
    function check(done) {
        Quickshell.execDetached(["which", "curl"], (exitCode, stdout) => {
            if (exitCode !== 0) {
                done({
                    title: "Missing Dependency: curl",
                    details: "Please install curl using your package manager:\n\nsudo pacman -S curl"
                });
            } else {
                done(null); // Gate passed
            }
        });
    }
}
```

---

## 5. Automated Manifest Validation Script

Add this validation script to your plugin's `tests/validate_manifest.py`:

```python
#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def validate():
    manifest_path = Path(__file__).resolve().parent.parent / "plugin.json"
    if not manifest_path.exists():
        sys.exit(f"Error: {manifest_path} not found")

    with open(manifest_path) as f:
        data = json.load(f)

    required_keys = ["id", "name", "description", "version", "author", "type", "capabilities"]
    for key in required_keys:
        if key not in data:
            sys.exit(f"Validation Error: Missing required key '{key}'")

    if data.get("settings") and "settings_write" not in data.get("permissions", []):
        sys.exit("Validation Error: Plugin has settings component but lacks 'settings_write' permission")

    print("SUCCESS: plugin.json passes structure & permission checks!")

if __name__ == "__main__":
    validate()
```
