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

Corner radii:
| Token | Value |
|---|---|
| `Theme.cornerRadiusSmall` | `6px` |
| `Theme.cornerRadius` | `12px` (User configurable standard) |
| `Theme.cornerRadiusLarge` | `18px` |

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
    width: 280
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
