# DMS Plugin Surfaces, Components & Settings Reference

This document details the exact QML APIs, lifecycle hooks, and properties for all DankMaterialShell plugin surfaces.

---

## 1. Bar Widgets & Control Center (`PluginComponent`)

`PluginComponent` (from `qs.Modules.Plugins`) is the base component for DankBar and Control Center integration.

### 1.1 Injected Host Properties
When DMS hosts your widget, it injects the following context properties into your `PluginComponent`:

```qml
// Orientation & Placement
axis.isVertical      // bool: true if bar is on left/right edge
axis.edge            // string: "top", "bottom", "left", "right"
section              // string: "left", "center", "right"
parentScreen         // Screen: Quickshell Screen reference
isFirst / isLast     // bool: first/last widget in current section

// Geometry & Dimensions
widgetThickness      // real: Recommended dimension perpendicular to bar
barThickness         // real: Overall thickness of the bar
barSpacing           // real: Margin/gap around the bar
barConfig            // var: User bar configuration (padding, iconScale, outlines)

// Scaled Sizing Helpers
iconSize             // int: Theme.barIconSize(barThickness, -4, ...)
iconSizeLarge        // int: Theme.barIconSize(barThickness, undefined, ...)

// Framework Services & Data
pluginId             // string: Plugin ID from plugin.json
pluginService        // var: Singleton PluginService reference
pluginData           // var: Reactive settings object from settings.json
popoutService        // var: Automatically injected PopoutService singleton
```

### 1.2 Surface Slots

```qml
PluginComponent {
    id: root

    // Popout dimensions
    popoutWidth: 420
    popoutHeight: 0 // 0 = dynamic content height

    // Top / Bottom DankBar
    horizontalBarPill: Component {
        Row {
            spacing: Theme.spacingXS
            DankIcon { name: "timer"; size: root.iconSize; color: Theme.primary }
            StyledText { text: "Time"; font.pixelSize: Theme.fontSizeSmall }
        }
    }

    // Left / Right DankBar
    verticalBarPill: Component {
        Column {
            spacing: Theme.spacingXS
            DankIcon { name: "timer"; size: root.iconSize; color: Theme.primary }
        }
    }

    // Popout panel
    popoutContent: Component {
        PopoutComponent {
            headerText: "My Timer"
            detailsText: "Session status"
            showCloseButton: true
            // Popout body...
        }
    }

    // Custom Click Actions (Optional)
    // IMPORTANT: If you accept positional arguments, DO NOT use JS default values (e.g. x = 0),
    // because DMS checks fn.length === 0. Default values cause fn.length to be 0!
    pillClickAction: (x, y, width, section, screen) => {
        // Custom left-click handler (overrides default popout toggle)
    }

    pillRightClickAction: (x, y, width, section, screen) => {
        // Custom right-click handler
    }
}
```

### 1.3 Control Center Tile Integration
A `PluginComponent` can double as a Control Center tile by setting these properties:

```qml
PluginComponent {
    id: root

    // CC Tile Presentation
    ccWidgetIcon: "wifi"
    ccWidgetPrimaryText: "Network"
    ccWidgetSecondaryText: "Connected"
    ccWidgetIsActive: true
    ccWidgetIsToggle: true // true = toggle button; false = action button

    onCcWidgetToggled: {
        // User clicked the main CC toggle button
    }

    onCcWidgetExpanded: {
        // User clicked chevron on a CompoundPill
    }

    // Optional dropdown detail panel (expands into a CompoundPill)
    ccDetailHeight: 250
    ccDetailContent: Component {
        Rectangle {
            color: Theme.surfaceContainerHigh
            radius: Theme.cornerRadius
            // Detail controls...
        }
    }
}
```

---

## 2. Desktop Widgets (`DesktopPluginComponent`)

Desktop widgets live on the desktop background layer (`WlrLayer.Bottom`).

```qml
import QtQuick
import qs.Common
import qs.Widgets
import qs.Modules.Plugins

DesktopPluginComponent {
    id: root

    minWidth: 160
    minHeight: 160

    // Force 1:1 aspect ratio on resize/init (Optional):
    // property bool forceSquare: true

    // Enable keyboard focus for text inputs in the widget:
    // property bool acceptsKeyboardFocus: true

    Rectangle {
        anchors.fill: parent
        radius: Theme.cornerRadius
        color: Theme.surfaceContainer

        // CRITICAL: Disable child interaction while user is in edit/drag mode:
        MouseArea {
            anchors.fill: parent
            enabled: !root.editMode
            onClicked: { /* Normal widget action */ }
        }
    }
}
```

### Desktop Widget Edit & Drag Mode Mechanics
- **Interaction**: Users enter edit mode by **Right-Click and Dragging** anywhere on the widget surface, or right-clicking the bottom-right 48x48px handle to resize.
- **Layer Promotion**: During dragging, the surface is temporarily promoted to `WlrLayer.Overlay` so it floats above all windows.
- **Keyboard Shortcuts while Dragging**:
  - `G`: Toggle grid snapping on/off.
  - `Z`: Decrease grid size by 10px (minimum 10px).
  - `X`: Increase grid size by 10px (maximum 200px).
- **Runtime Resizing API**:
  - `requestResize(width, height)`: Temporarily resizes the window surface at runtime without writing to disk.
  - `clearResize()`: Reverts to the user's saved dimensions.

---

## 3. Headless Daemons (`daemon`)

Daemons are background singletons instantiated once on DMS startup.

```qml
import QtQuick
import Quickshell.Io
import qs.Common
import qs.Services
import qs.Modules.Plugins

Item {
    id: root

    // Injected by framework:
    property string pluginId: ""
    property var pluginService: null
    property var popoutService: null

    // Register IPC endpoints callable via: dms ipc call myDaemon toggle
    IpcHandler {
        target: root.pluginId

        function toggle(): string {
            return "TOGGLED";
        }
    }

    // Monitor shell events
    Connections {
        target: SessionData
        function onWallpaperPathChanged() {
            // React to wallpaper change
        }
    }
}
```

---

## 4. Application Launcher Plugins (`launcher`)

Launcher plugins feed items into the DMS App Launcher / Spotlight.

```qml
import QtQuick
import Quickshell
import qs.Services

Item {
    id: root

    property var pluginService: null
    property string trigger: "#" // Prefix trigger from manifest

    signal itemsChanged() // Notify launcher to re-query

    function getItems(query) {
        return [
            {
                name: "Command Name",
                icon: "material:terminal", // "material:name", "unicode:🚀", or desktop icon
                comment: "Subtitle or description",
                action: "exec:foot",
                categories: ["MyCategory"]
            }
        ];
    }

    function executeItem(item) {
        if (item.action.startsWith("exec:")) {
            Quickshell.execDetached([item.action.replace("exec:", "")]);
        }
    }
}
```

---

## 5. Declarative Settings Controls (`PluginSettings`)

DMS includes built-in declarative setting components in `qs.Modules.Plugins`. They automatically read saved values on start and persist changes on edit.

> [!IMPORTANT]
> `plugin.json` must declare `"permissions": ["settings_read", "settings_write"]`, or `PluginSettings` will display an access violation error.

```qml
import QtQuick
import qs.Common
import qs.Widgets
import qs.Modules.Plugins

PluginSettings {
    id: root
    pluginId: "myPlugin"

    // 1. Text String
    StringSetting {
        settingKey: "username"
        label: "Username"
        description: "Your service account handle"
        placeholder: "quantavil"
        defaultValue: ""
    }

    // 2. Toggle Switch
    ToggleSetting {
        settingKey: "enableSounds"
        label: "Sound Alerts"
        description: "Play completion chimes"
        defaultValue: true
    }

    // 3. Dropdown Selection
    SelectionSetting {
        settingKey: "refreshInterval"
        label: "Refresh Rate"
        description: "Polling frequency"
        options: [
            { label: "30 Seconds", value: "30" },
            { label: "1 Minute",   value: "60" },
            { label: "5 Minutes",  value: "300" }
        ]
        defaultValue: "60"
    }

    // 4. Numeric Slider
    SliderSetting {
        settingKey: "opacity"
        label: "Background Opacity"
        minimum: 10
        maximum: 100
        unit: "%"
        defaultValue: 90
        leftIcon: "opacity"
    }

    // 5. Material Color Picker
    ColorSetting {
        settingKey: "accentColor"
        label: "Accent Color"
        defaultValue: Theme.primary
    }

    // 6. Structured Table / List Editor
    ListSettingWithInput {
        settingKey: "shortcuts"
        label: "Custom Shortcuts"
        defaultValue: []
        fields: [
            { id: "key", label: "Key", width: 100, placeholder: "Ctrl+K", required: true },
            { id: "command", label: "Command", width: 250, placeholder: "app-launch", required: true }
        ]
    }
}
```
