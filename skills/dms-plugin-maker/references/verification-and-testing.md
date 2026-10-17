# DMS Verification and Regression Testing

Select checks for the behavior under change. Testing a simple widget does not
require inventing an engine. Execute tests when the task authorizes verification;
report missing tools and untested layers honestly.

## Pure calculations

Use deterministic times and plain snapshots. Assert transitions and emitted events,
not just formatted strings. For timers cover pause/resume, zero/boundary values,
delayed ticks spanning several phases, next-day alarms, repeated starts, completion
exactly once, dismissal, and reset. Include clock changes when the chosen clock
semantics require them. Load QML JS in an isolated module/context if it lacks
CommonJS exports; avoid changing global loaders or adding production test hooks.

## State bridge and runtime QML

Exercise actual bridge methods with controlled time and stubbed host effects.
Use Qt runtime tests for actual bindings, focus, visibility, geometry, and event
routing. Stub unavailable DMS boundaries, not the component logic being tested.
Pure JS extraction cannot prove QML lifecycle or binding behavior.

Regression matrix for shared interactive timers:

| Scenario | Required observation |
|---|---|
| Multiple widget instances | One effect/save owner; all views share state |
| Owner removed | Surviving instance takes ownership without replaying effects |
| Settings hydration/reload | No startup saves; active/paused/completed progress preserved |
| Temporary IPC configuration | Repeated starts follow contract; reset restores saved defaults |
| Alarm ringing then dismissed | Sound/timer stop and alarm stays dismissed |
| Numeric editor commit/cancel | Binding restored; later model changes appear |
| Typing Space or R | Global start/reset shortcut does not fire |
| Every mode/state | Content fits; available actions match state |
| Font 1.5x/2x, corner zero | No clipped fields/actions; custom controls follow Theme |
| Fullscreen reminder | Created only on intended completion; removed on dismiss/reset |

Prefer tests that catch a known regression. Remove duplicates and assertions about
incidental source text. Keep static checks for actual static contracts, such as
literal translation IDs. Mutation checks can establish whether critical tests
catch a deliberately broken transition; restore changes immediately. Report
behavioral cases separately from setup/cleanup hooks rather than inflating counts.

## QML lint and manifest schema

Locate qmllint in PATH or Qt's bin directory; add import paths for the plugin, Qt,
and the active DMS runtime. Do not disable import checking to get a green result.
Lint all shipped components. Missing tools/imports are unavailable checks, not a
pass. Lint cannot prove live focus, rendering, or singleton lifecycle behavior.

Validate plugin.json with a JSON Schema validator against the installed DMS
`PLUGINS/plugin-schema.json`, an explicitly selected schema, or a maintained pinned
fallback. State the schema source. Required-key checks alone are not schema
validation. Also verify referenced files exist and IDs agree across entry points.

## Authorized live deployment

Inspect the existing plugin installation before replacing it. Back up settings
and installation paths before migration or temporary preference changes. Use a
symlink for an authorized local development install when appropriate. Query the
installed plugin through its actual IPC contract; wait for shell readiness rather
than trusting a fixed delay alone.

Plugin reload may retain cached QML classes or singleton state. Restart DMS when
checking changed singleton/class definitions if reload does not pick them up.
Inspect logs for ReferenceError, TypeError, binding loops, and missing properties.
Observe each mode and relevant running/paused/completed state, keyboard editing,
completion effects, and overlay dismissal. Check per-screen overlay count and
keyboard focus policy. Headless simulated monitors do not establish physical
multi-monitor or cross-compositor compatibility.

Restore temporary font scale, sounds, reminder flags, durations, and other user
preferences, then verify restoration. Reconcile disk edits with in-memory settings;
external edits may require a restart. Capture screenshots only after confirming
that they represent the current deployed code.
