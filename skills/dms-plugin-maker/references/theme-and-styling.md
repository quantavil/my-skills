# DMS Material 3 Theme & Styling Reference

DMS features a dynamic, wallpaper-aware Material 3 theming system powered by Matugen. Plugins must use the `Theme` singleton (imported from `qs.Common`) to guarantee visual consistency and automatic light/dark mode adaptation.

---

## 1. Material 3 Color Roles

### Surface Elevation Hierarchy
Use surface containers according to their elevation:

| Token | Recommended Purpose |
|---|---|
| `Theme.surface` | Base desktop / fullscreen background surface |
| `Theme.surfaceContainerLowest` | Deepest layer (input troughs, depressed areas) |
| `Theme.surfaceContainerLow` | Low elevation container |
| `Theme.surfaceContainer` | Default card, dialog, and popout background |
| `Theme.surfaceContainerHigh` | Elevated container: bar pills, buttons, inner cards |
| `Theme.surfaceContainerHighest` | Highest elevation: modals, floating tooltips |

### Content & Text
| Token | Description |
|---|---|
| `Theme.surfaceText` (or `Theme.onSurface`) | Primary high-contrast text and icons |
| `Theme.surfaceVariantText` (or `Theme.onSurfaceVariant`) | Secondary/muted labels and icons |
| `Theme.surfaceTextSecondary` | 60% opacity surface text (`withAlpha(surfaceText, 0.6)`) |
| `Theme.surfaceTextMedium` | 70% opacity surface text (`withAlpha(surfaceText, 0.7)`) |
| `Theme.onSurface_38` | Disabled text and icons (38% opacity) |

### Accent Roles
| Token | Description |
|---|---|
| `Theme.primary` | Primary accent color |
| `Theme.primaryText` (or `Theme.onPrimary`) | Text placed directly on a `Theme.primary` background |
| `Theme.primaryContainer` | Subtle primary tonal container |
| `Theme.secondary` / `Theme.onSecondary` | Secondary accent |
| `Theme.secondaryContainer` | Secondary tonal container |
| `Theme.tertiary` / `Theme.tertiaryContainer` | Tertiary accent |

### Semantic & Alert Roles
| Token | Value / Purpose |
|---|---|
| `Theme.error` | Critical alerts / destructive actions (default `#F2B8B5`) |
| `Theme.warning` | Warnings (default `#FF9800`) |
| `Theme.info` | Informational notices (default `#2196F3`) |
| `Theme.success` | Confirmations / positive completion (default `#4CAF50`) |

### Borders & Outlines
| Token | Description |
|---|---|
| `Theme.outline` | Standard high-contrast border |
| `Theme.outlineVariant` | Low-contrast subtle border (`withAlpha(outline, 0.6)`) |
| `Theme.outlineStrong` | Active/focused border |

---

## 2. Typography & Fonts

All typography scales automatically when user adjusts system font scaling:

| Token | Scaled Pixel Size | Default Font Family |
|---|---|---|
| `Theme.fontSizeSmall` | `12px` | `Theme.fontFamily` ("Inter Variable") |
| `Theme.fontSizeMedium` | `14px` | `Theme.fontFamily` |
| `Theme.fontSizeLarge` | `16px` | `Theme.fontFamily` |
| `Theme.fontSizeXLarge` | `20px` | `Theme.fontFamily` |
| `Theme.monoFontFamily` | — | Monospace ("Fira Code") |

---

## 3. Spacing & Metrics

Spacing tokens are abbreviated (`XXS` through `XL`):

| Token | Value |
|---|---|
| `Theme.spacingXXS` | `2px` |
| `Theme.spacingXS` | `4px` |
| `Theme.spacingS` | `8px` |
| `Theme.spacingM` | `12px` |
| `Theme.spacingL` | `16px` |
| `Theme.spacingXL` | `24px` |

Corner radii (verify against the installed Theme; `cornerRadiusSmall` and
`cornerRadiusLarge` were absent in the runtime used for DankClockwork):
| Token | Value |
|---|---|
| `Theme.cornerRadius` | `12px` (User configurable standard) |

Icon sizes:
| Token | Value |
|---|---|
| `Theme.iconSizeSmall` | `16px` |
| `Theme.iconSize` | `24px` |
| `Theme.iconSizeLarge` | `32px` |

---

## 4. Theme Utility Functions

```qml
// Apply opacity to any color:
Theme.withAlpha(Theme.primary, 0.5)

// Linear blend between two colors (ratio 0.0 - 1.0):
Theme.blend(Theme.surfaceText, Theme.primary, 0.2)

// Hover state tint (lightens in dark mode, darkens in light mode):
Theme.hoverTint(Theme.surfaceContainerHigh)

// Pixel snapping for crisp rendering on fractional scale displays:
Theme.snap(rawPosition, dpr)
Theme.snapEven(rawSize, dpr) // Prevents 0.5px centering blur
```

---

## 5. Standard Widget Construction

```qml
import QtQuick
import qs.Common
import qs.Widgets

StyledRect {
    id: card
    width: Theme.fontSizeMedium * 20
    implicitHeight: col.implicitHeight + Theme.spacingL * 2
    radius: Theme.cornerRadius
    color: Theme.surfaceContainerHigh
    border.color: Theme.outlineVariant
    border.width: 1

    Column {
        id: col
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Theme.spacingL
        spacing: Theme.spacingS

        Row {
            spacing: Theme.spacingXS
            DankIcon {
                name: "notifications"
                size: Theme.iconSizeSmall
                color: Theme.primary
            }
            StyledText {
                text: I18n.tr("Notifications")
                font.pixelSize: Theme.fontSizeMedium
                font.weight: Font.Bold
                color: Theme.surfaceText
            }
        }

        StyledText {
            text: I18n.tr("All services operational.")
            font.pixelSize: Theme.fontSizeSmall
            color: Theme.surfaceVariantText
            wrapMode: Text.WordWrap
            width: parent.width
        }
    }
}
```


## Adaptive popouts and focused controls

- Use Theme tokens for margins, spacing, fonts, icons, and custom control radii.
  A smaller radius can be `Theme.cornerRadius / 2`; it must also become zero when
  the user chooses square corners. Literal hairline widths and dimensionless
  ratios can be appropriate; raw pixel card geometry is not a scaling strategy.
- Build card height from measured readout/editor height, status height, and
  padding. Derive popout width from text/control needs or allow responsive sizing.
  A fixed minimum can serve a real constraint; equal empty space across modes
  does not establish visual consistency.
- Check default, 1.5x, and 2x font scale, square corners, narrow screens, long
  values, and light/dark themes. Fixed offsets, steppers, action widths, and
  overlay text need scrutiny as well as labels.
- For time readouts, use the theme font with tabular numbers when supported
  (`font.features: { "tnum": 1 }`). Explicitly style TextInput selection with
  themed selection and selected-text colors; native defaults can introduce an
  unrelated bright blue highlight. Keep focus visible and text readable.
- Give active tabs one clear persistent indicator (for example accent text and
  an underline), plus distinct hover and focus states. Choose this to fit the
  interface; it is not a requirement that every DMS plugin use underlined tabs.
- Put a contextual display toggle near the display it affects, with tooltip,
  checked state, accessible meaning, and a usable hit target. A fullscreen
  reminder toggle need not consume a full configuration row.
- Keep action placement consistent. Show valid actions for the session state;
  disable reset at an untouched idle state if it has no effect. Avoid repeating
  the same status in the header, hero, and explanatory copy.
- Audit settings against popout controls. Session durations should normally be
  edited where users start sessions. Keep durable preferences in settings and
  use the same setter/persistence path. Do not retain two editable versions of
  one value unless the distinction is explicit and useful.


## Sound and accessibility tradeoffs

Completion sounds need an explicit product contract: one chime for a timer,
repeated ringing for an alarm when appropriate, and a discoverable dismiss action.
Dismissing a current alarm and muting future alarms are different operations.
Remove dead or redundant sound controls; do not forbid intentional quiet modes
when users need them. Pair important audio with visible status/notification so
sound is not the only completion signal. Show keyboard focus, explain icon-only
controls, and verify contrast with the user's light/dark theme.
