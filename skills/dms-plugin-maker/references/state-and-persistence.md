# DMS State Management, Persistence & Multi-Instance Synchronization

DMS plugins have unique lifecycle and multi-monitor execution characteristics. Choosing the correct storage channel is essential for stability and performance.

---

## 1. The 4 Data Channels

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STATE ARCHITECTURE                                 │
├──────────────────┬─────────────────┬───────────────────┬────────────────────────┤
│ Mechanism        │ Scope           │ Storage Location  │ Primary Purpose        │
├──────────────────┼─────────────────┼───────────────────┼────────────────────────┤
│ PluginSettings / │ Persistent      │ settings.json     │ User preferences, API  │
│ pluginData       │ (survives boot) │ (pluginSettings)  │ keys, UI toggles       │
├──────────────────┼─────────────────┼───────────────────┼────────────────────────┤
│ pluginState      │ Persistent      │ <id>_state.json   │ Application data,      │
│ API              │ (survives boot) │ in ~/.local/state │ history, notes, caches │
├──────────────────┼─────────────────┼───────────────────┼────────────────────────┤
│ PluginGlobalVar  │ In-Memory       │ RAM only          │ Multi-monitor sync,    │
│                  │ (session only)  │ (PluginService)   │ widget-daemon comms    │
├──────────────────┼─────────────────┼───────────────────┼────────────────────────┤
│ IpcHandler       │ Remote/Process  │ Unix domain sock  │ CLI triggers (dms ipc) │
│                  │ (RPC)           │ / Quickshell IPC  │ and external hooks     │
└──────────────────┴─────────────────┴───────────────────┴────────────────────────┘
```

---

## 2. Channel 1: Persistent Configuration (`pluginData`)

- Stored in: `~/.config/DankMaterialShell/settings.json`.
- Access in components: `root.pluginData.myKey`.
- Programmatic save: `pluginService.savePluginData(pluginId, key, value)`.
- Intended for: User options, flags, API endpoints.

---

## 3. Channel 2: Application Data Cache (`pluginState`)

Avoid polluting user configuration with dynamic data arrays, note histories, or cached payloads. Use the dedicated `pluginState` API:

- Stored in: `~/.local/state/quickshell/dms/plugins/<id>_state.json`.
- Automatically uses debounced atomic disk writes.

```qml
// Save large array or state payload
pluginService.savePluginState(pluginId, "noteHistory", notesArray);

// Load on initialization
property var noteHistory: pluginService.loadPluginState(pluginId, "noteHistory", [])

// Remove specific key
pluginService.removePluginStateKey(pluginId, "tempCache");

// Clear all plugin state
pluginService.clearPluginState(pluginId);
```

---

## 4. Channel 3: In-Memory Multi-Monitor Sync (`PluginGlobalVar`)

When a user has two monitors, DMS instantiates two independent copies of your `PluginComponent` (one for each DankBar). If the user starts a timer on Screen 1, Screen 2 must reflect it immediately.

Use `PluginGlobalVar` (from `qs.Widgets`) or `PluginService.setGlobalVar`:

```qml
import QtQuick
import qs.Widgets

Item {
    // Shared variable synchronized reactively across all monitors and daemons
    PluginGlobalVar {
        id: sessionActive
        varName: "sessionActive"
        defaultValue: false
    }

    StyledText {
        text: sessionActive.value ? "Active" : "Idle"
    }

    MouseArea {
        anchors.fill: parent
        onClicked: sessionActive.set(!sessionActive.value)
    }
}
```

---

## 5. Channel 4: CLI IPC (`IpcHandler`)

Enables compositor keybindings, terminal scripts, or foreign tools to interact with your plugin:

```qml
IpcHandler {
    target: "myPlugin"

    function toggle(): string {
        root.startPause();
        return root.running ? "CLOCKWORK_RUNNING" : "CLOCKWORK_PAUSED";
    }

    function status(): string {
        return JSON.stringify({
            running: root.running,
            time: root.displayText
        });
    }
}
```
* Invoke via terminal: `dms ipc call myPlugin toggle` or `dms ipc call myPlugin status`.

---

## 6. The Multi-Instance Startup Hydration Rule

### The Problem
When the shell starts up, DMS instantiates `Widget.qml` on every connected monitor. Both instances read `pluginData` and call property setters. If those setters unconditionally emit `saveSetting`, both widgets immediately trigger concurrent disk writes for values that were just loaded!

### The Solution
Always accept an optional `notifyHost` flag in state mutators. Pass `false` during startup hydration in `Widget.qml` and `Settings.qml`:

```qml
// Inside State.qml singleton:
function setDurationMinutes(value, notifyHost) {
    var v = Math.max(1, Number(value) || 1);
    if (root.durationMinutes === v) return;
    root.durationMinutes = v;
    
    // Only notify host / write to disk if user initiated the change
    if (notifyHost === undefined || notifyHost) {
        root.settingSaveRequested("durationMinutes", v);
    }
}

// Inside Widget.qml:
function applySettings() {
    // Pass false to suppress re-saving to disk on boot:
    stateSingleton.setDurationMinutes(pluginData.durationMinutes ?? 25, false);
}
Component.onCompleted: applySettings()
onPluginDataChanged: applySettings()
```

---

## 7. The Variants System (`ExampleWithVariants`)

The Variants feature allows one plugin to spawn multiple independent instances on the bar (e.g. multiple distinct world clocks, crypto tickers, or script buttons).

### ID Scheme
- Base plugin: `myPlugin`
- Variant instance: `myPlugin:variant_1700000000000`

### Injected Variant Properties
In `Widget.qml`:
```qml
PluginComponent {
    id: root

    // Host automatically extracts and injects these:
    property string variantId: ""       // Empty for base widget; string for variant
    property var variantData: null      // Object holding this variant's custom config

    property string displayText: variantData?.text || pluginData.defaultText || "Default"
}
```

### Variant Management in `Settings.qml`
`PluginSettings` provides built-in variant CRUD:
```qml
PluginSettings {
    id: root
    pluginId: "myPlugin"

    function addInstance(name, customText) {
        root.createVariant(name, { text: customText });
    }

    ListView {
        model: root.variantsModel // Built-in ListModel
        delegate: Row {
            StyledText { text: model.name }
            DankButton {
                iconName: "delete"
                onClicked: root.removeVariant(model.id)
            }
        }
    }
}
```
