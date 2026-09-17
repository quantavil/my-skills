# DMS Plugin Framework Traps, Quirks & Gotchas

This document contains real-world traps, undocumented implementation quirks, and subtle framework edge cases identified across the DankMaterialShell codebase.

---

### Trap 1: The Function Arity Dispatch Trap (`pillClickAction`)
- **The Issue**: `PluginComponent` inspects `pillClickAction.length` to choose between calling `pillClickAction()` (0 args) vs passing positional geometry `pillClickAction(x, y, width, section, screen)` (>0 args).
- **The Catch**: In JavaScript, default parameter syntax (e.g. `(x = 0, y = 0) => ...`) sets `Function.length` to `0`!
- **Consequence**: The framework assumes 0 arguments are expected and calls it with **no arguments**, leaving all parameters undefined.
- **Rule**: Never use default parameters on `pillClickAction` or `pillRightClickAction`:
  ```qml
  // BAD: length is 0!
  pillClickAction: (x = 0, y = 0, width = 0) => { ... }

  // GOOD: length is 5
  pillClickAction: (x, y, width, section, screen) => { ... }
  ```

---

### Trap 2: Missing `isInitialized` in Setting Components
- **The Issue**: `ToggleSetting`, `StringSetting`, and `ColorSetting` use an internal `isInitialized` guard to prevent saving during initial startup loading. However, `SliderSetting`, `SelectionSetting`, and `ListSetting` **lack** this guard in their `onValueChanged` handlers.
- **Consequence**: If your QML dynamically computes or modifies the `value` of a `SliderSetting` during initialization, `saveValue()` triggers prematurely, clobbering existing saved user settings with defaults.
- **Rule**: Set values on setting components only in response to explicit user input.

---

### Trap 3: Popout Height Collapsing (`popoutHeight: 0`)
- **The Issue**: `PluginComponent` defaults `popoutHeight` to `0` to signal dynamic auto-sizing. `PluginPopout` binds window height to:
  ```javascript
  contentHeight = item.implicitHeight + Theme.spacingS * 2;
  ```
- **Consequence**: If the root element inside `popoutContent` lacks an explicit or calculated `implicitHeight`, `item.implicitHeight` evaluates to `0` and the popout renders as an empty 16px sliver.
- **Rule**: Always ensure child layouts inside `popoutContent` set `implicitHeight: myLayout.implicitHeight`.

---

### Trap 4: Color Serialization Format (`ColorSetting`)
- **The Issue**: QML `color` objects serialize to `{}` when converted via generic JS `JSON.stringify()`.
- **Consequence**: Storing a raw color object writes `{}` to `settings.json`. On the next shell boot, assigning `{}` to a `property color` causes a silent QML type error and resets the color to black/transparent.
- **Rule**: Always serialize colors as hex strings via `.toString()` (e.g. `"#ffffffff"`):
  ```qml
  pluginService.savePluginData(pluginId, "myColor", myColor.toString());
  ```

---

### Trap 5: Parent Chain Breakage in Settings Layouts
- **The Issue**: Setting components find their persistence host using `QmlUtils.findSettings(root.parent)`, traversing up the visual hierarchy until an item with `saveValue` and `loadValue` is found.
- **Consequence**: If a setting component is placed inside an unparented `Item`, a detached `Component`, or a nested visual structure that doesn't propagate `parent`, `findSettings()` returns `null`, and the setting silently fails to load or save.
- **Rule**: Place setting components directly inside `PluginSettings` or inside direct child containers (`Column`, `ColumnLayout`).

---

### Trap 6: Missing `settings_write` Permission
- **The Issue**: `PluginSettings.qml` checks `hasPermission` before rendering controls.
- **Consequence**: If `plugin.json` omits `"permissions": ["settings_read", "settings_write"]`, `PluginSettings` displays an access violation error banner and completely disables saving.
- **Rule**: Any plugin with a settings component must explicitly request `settings_write` in `plugin.json`.

---

### Trap 7: Clipboard Access Misconceptions
- **The Issue**: Developers frequently attempt to use web APIs like `navigator.clipboard.writeText(...)` or Node-style utilities.
- **Consequence**: These APIs do not exist in the QML runtime and crash execution.
- **Rule**: Always use the native DMS clipboard CLI bridge:
  ```qml
  Quickshell.execDetached(["dms", "cl", "copy", textToCopy]);
  ```

---

### Trap 8: Desktop Widget Keyboard Focus
- **The Issue**: By default, desktop widget layer surfaces specify `WlrLayershell.keyboardFocus: WlrKeyboardFocus.None`.
- **Consequence**: Text inputs (`TextInput`, `TextField`) inside desktop widgets cannot receive focus or keyboard input.
- **Rule**: The desktop widget root must declare:
  ```qml
  property bool acceptsKeyboardFocus: true
  ```
  The wrapper will then dynamically request `WlrKeyboardFocus.OnDemand`.

---

### Trap 9: The `editMode` Documentation Trap
- **The Issue**: Older DMS documentation claims `DesktopPluginWrapper` injects `property bool editMode: false`.
- **The Reality**: The wrapper manages dragging and resizing exclusively on `Qt.RightButton`. It never imperatively mutates child `editMode`.
- **Rule**: Do not rely on `editMode` to toggle UI. Simply let child left-click handlers work normally—the wrapper will capture right-clicks for positioning.

---

### Trap 10: `I18n.trFor` String Literal Rule
- **The Issue**: DMS uses static AST extraction to discover translatable strings for plugins.
- **Rule 1**: The first argument in `I18n.trFor("myPluginId", "String to translate")` MUST be an exact string literal matching your manifest `id`. Never pass a variable or property reference.
- **Rule 2**: Do not create an `en.json` file. The QML source string is the default English source.
- **Rule 3**: Plugin translations must be placed in `translations/<locale>.json` (e.g. `es.json`, `de.json`, `zh_CN.json`).

---

### Trap 11: Startup Gate (`startupCheck`) Visual Item Crash
- **The Issue**: Declaring an `Item` or `Rectangle` as the root of `startupCheck`.
- **Consequence**: Visual components instantiated outside of a scene graph during startup checks can cause Wayland surface allocation crashes.
- **Rule**: `startupCheck` must always be a non-visual `QtObject`.

---

### Trap 12: `BasePill` Screen Edge Hitbox Expansion (Fitts's Law)
- **The Issue**: To make edge widgets easy to hit, `BasePill` automatically extends its background hitbox by `1000px` towards the screen edge when touching the border of the bar (`isLeftBarEdge && isFirst`, etc.).
- **Consequence**: Clicks on the outer monitor bezel trigger the top-level pill. However, child `MouseArea` elements inside your custom pill content do **not** inherit this 1000px expansion.
