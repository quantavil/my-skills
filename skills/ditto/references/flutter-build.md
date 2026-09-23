# Writing the Flutter code

Use the existing architecture and [flutter-stack.md](flutter-stack.md) for dependency choices. Implement observed behavior; no state wrapper automatically fixes networking, ordering and persistence bugs.

## Convert capture pixels to logical dimensions

On Android, `capture_dpr = density_dpi / 160` and `logical_px = physical_px / capture_dpr`. Read density from the capture's environment, not the rendering device. For iOS, use the recorded capture scale, not the Android dpi formula. A resized screenshot cannot provide trustworthy native measurements.

At 420 dpi, a 132 px button is `132 / 2.625 = 50.28` logical pixels. Confirm any rounding against the original. Convert once during measurement; do not put runtime device-pixel-ratio corrections into layout constants.

Glyph height is not `fontSize`: font metrics, line height and text scaling intervene. Use extracted fonts and confirm text at matching scale. Keep safe-area insets separate from content padding.

## Reuse confirmed tokens

Reuse the project's token file. When repeated measurements justify automation, run `theme_extract.py` on representative captures of the same theme and density:

See [measurement commands](commands.md#measurement).

Supply actual paths; omit `--hierarchy` when unavailable. Write `--json` only for a consumer that needs it, rather than maintaining a duplicate token record. This tool clusters colours and selects observed pixel colours as representatives. It suggests roles and nearest-neighbour gaps across hierarchy bounds, not declared theme values or guaranteed sibling spacing. Exclude photographs/system UI from interpretation, separate dark/light themes, and verify generated values before using them. PNG compression is lossless; blending and source images can still affect rendered colours.

Use confirmed values in `ThemeData` and explicit `ColorScheme` roles. A generated seed palette can differ from the original even when its seed matches. Update tokens only when new evidence changes them; do not rerun extraction after every screenshot.

## Implement a phase as a vertical Flutter feature

This reference incorporates the Flutter architecture, layout, routing, localization, networking, and testing guidance needed for a Ditto clone. For each phase, map captured actions and states to the existing code before editing. A useful implementation order is model/fixture → service or platform adapter → repository → state controller → screen/widgets → route integration. Keep the original's visible transitions as the contract. Do not create every layer for a trivial local screen, or replace a working architecture merely to match a template.

| Responsibility | Put here | Check against original evidence |
| --- | --- | --- |
| View/widgets | Layout, focus, animations, user input; render the current state | Text, bounds, touch targets, keyboard, semantics, loading/error/empty states |
| Controller/view model/provider | Events, async ordering, selected tab, pending state | Which action changes which state, and when |
| Repository | Cache, durable writes, mapping, offline/retry policy | Restart behavior, stale data, duplicate submits, error recovery |
| Service/platform adapter | HTTP, database, Android/iOS APIs | Request/response shape, permission and lifecycle behavior |

Inject the repository or adapter at the existing seam so deterministic fixtures can drive widget tests. Keep fixture mode explicit: a successful fake response is not proof that the live integration matches the original. Use immutable state snapshots where the current state library supports them. For a new project, [flutter-stack.md](flutter-stack.md#implement-a-vertical-feature) gives the directory shape; for an existing project, follow its conventions.

## Build and diagnose layouts

1. Start from the captured hierarchy and screenshot at a recorded viewport, density, locale, text scale, and system-bar setup. Build the widget tree around the same content and scroll regions. Convert physical dimensions once as described above; do not compensate with arbitrary offsets.
2. Apply the extracted font, asset, colors, and spacing tokens. Preserve intrinsic image fit/crop, text baseline and line height, and status/navigation bar insets. Check screen states with long strings, errors, and the soft keyboard before polishing one static screenshot.
3. Use `LayoutBuilder` when a child must respond to its *parent's available width*. Use `MediaQuery.sizeOf(context)` for the app window; neither is a substitute for measuring the captured original. Add alternate layouts only for sizes that the phase actually covers.
4. For a `Row` with a text field or long label, give the growing child `Expanded` or `Flexible`. For a `Column` containing `ListView`/`GridView`, give the scrollable a bounded height (`Expanded`, a suitable `SizedBox`, or a sliver structure). Use lazy builders for long lists, stable keys for stateful rows, and preserve observed scroll position.
5. When Flutter reports `RenderFlex overflowed`, an unbounded viewport, or an unlaid `RenderBox`, inspect the *first* constraint error and its parent/child pair. Fix the constraint or content flow; clipping, `shrinkWrap`, or smaller text should not conceal content that the original displays. Recheck with the same keyboard and text-scale state.

For example, a `TextField` beside an icon in a `Row` needs a width constraint:

```dart
Row(children: [
  const Icon(Icons.search),
  Expanded(child: TextField(controller: searchController)),
])
```

## Reproduce navigation and restoration

Record each observed route's entry action, arguments, visible shell, tab/stack behavior, modal behavior, and result on system back. Keep Navigator for a simple existing flow. When the app already uses `go_router`, map routes with `GoRoute`; use persistent shell branches only if switching tabs in the original preserves separate stacks. Keep auth redirects and missing/deleted-item handling explicit. Do not infer deep links merely from a route name: confirm package intent filters and runtime behavior before implementing them.

Test navigation from a fresh install or cold start, after app background/return, and after process restart where the phase requires it. A hot-reload session may retain state that the installed APK does not. Capture the final destination and back result through the controller MCP, then compare with the original pack.

## Localize observed content

Reuse the project's localization setup. If observed locales require new support, add `flutter_localizations` from the Flutter SDK, keep strings in ARB files, set `flutter: generate: true` in `pubspec.yaml`, and configure supported locales and localization delegates on `MaterialApp`/`CupertinoApp`. Define the ARB directory and template in `l10n.yaml`, run localization generation, and use the generated accessor inside the app's localization scope. Check the installed Flutter version's generated import path and l10n options instead of copying a stale `synthetic-package` example. Keep placeholders, plurals, selects, and date/number formatting typed and localized rather than concatenating translated fragments.

Map each captured string to its locale and state. Extracted APK strings are candidates: runtime text may come from a server, formatting rule, or embedded web content. Compare at the same locale, text scale, font and direction. Verify long labels, plural quantities, empty/error messages, and right-to-left layout only when the original supports them.

## Implement data and platform behavior

Keep network and storage behind the existing service/repository boundary. Build URIs with typed query parameters and inject the client so the phase fixture can be replayed. Decode JSON into typed models, preserving missing versus explicit `null`, enum spelling, numeric types, timestamps, and the original's error bodies. For a small stable model, a checked `fromJson`/`toJson` pair is sufficient; use the project's generator when wire models repeat. Parse large payloads off the UI isolate only when measured parsing work affects frames.

Check success by the observed endpoint contract, not one universal HTTP status code. Surface status/parse/timeout errors as distinct states if the original does; never silently turn a failed request into empty success. Do not trigger a new fetch on every widget rebuild. Before implementing refresh, login renewal, or writes, follow the ordering and durability rules below. Platform calls belong in an adapter with permission, lifecycle, cancellation, and error outcomes that the controller can exercise.

## Test and debug the clone

Choose tests for failure modes that matter to the phase:

| Test | Good target | Boundary |
| --- | --- | --- |
| Unit (`test/`) | JSON absent/null cases, state transitions, stale response, duplicate submit, repository retry | A mock proves clone logic, not original parity |
| Widget (`test/`) | Input → action → loading/data/error render, focus, scrolling to a lazy item, navigation callback | Fix locale, font, viewport and injected fixture for stable assertions |
| Integration (`integration_test/`) | A candidate app journey, back/restart behavior, plugin interaction | Run on the intended local device; fixture journeys do not prove live backend behavior or original parity |

Use `WidgetTester` to pump the screen, find by visible text/key, enter text or tap, then pump the expected transition and assert the resulting state. For continuous animations, advance a bounded duration instead of waiting indefinitely with `pumpAndSettle`. Add stable keys only where text/type selection is ambiguous. Mirror feature paths under `test/`, ending files in `_test.dart`; use simple fakes before introducing generated mock machinery. Run `integration_test/` on the intended emulator with the project's Flutter test command; use the controller MCP separately for package-bound original/clone capture.

On a failure, capture the first useful analyzer diagnostic, Flutter layout exception, or runtime stack frame. Trace it to the responsible input, state transition, or constraint and fix that cause. Preview project-wide automated fixes before applying them. Run formatting, analysis, affected tests, and a fresh installed build in the batch described below. Tests protect clone behavior; the original/clone/diff evidence pack decides parity.

## Async state and durable effects

Treat these as separate contracts with separate checks:

- Search: key state by query, cancel obsolete work where supported, and guard manual state writes against stale request completion and disposal. Check the installed state library's lifecycle semantics.
- Submit: prevent re-entry while pending; enforce idempotency at the repository/server boundary where observed. A disabled button alone is insufficient.
- Refresh: retain cached content with an explicit refreshing/error state when the original does so. Test overlapping refreshes, not just one successful request.
- Authentication: share a refresh in flight, exclude the refresh request from retry interception, apply the new token and bound retries. A second unauthorized response ends the attempt.
- Offline writes: acknowledge only the durability level actually reached. Distinguish locally persisted/pending from server-confirmed; preserve observed retry and restart semantics.

`AsyncValue` can represent loading/data/error, but does not provide these contracts by itself. Use APIs supported by the project's locked Riverpod version and avoid adding code generation merely for these examples.

### Bounded session refresh example

This dependency-free Dart example wraps a replayable read. The injected `read` adapter translates HTTP 401 into `Unauthorized` and sends the supplied token. The injected `refresh` adapter uses a separate HTTP path/client that never calls this wrapper. Instantiate one reader per session; discard it on logout. Apply only if one refresh/retry matches observed behavior. Do not extend it to writes without an idempotency contract.

```dart
class Unauthorized implements Exception {}

class SessionReader<T> {
  SessionReader({
    required String token,
    required Future<T> Function(String token) read,
    required Future<String> Function() refresh,
  }) : _token = token, _read = read, _refresh = refresh;

  String _token;
  final Future<T> Function(String token) _read;
  final Future<String> Function() _refresh;
  Future<String>? _refreshing;

  Future<String> _freshToken() async {
    final pending = _refreshing ??= Future<String>.sync(_refresh);
    try {
      return _token = await pending;
    } finally {
      if (identical(_refreshing, pending)) _refreshing = null;
    }
  }

  Future<T> read() async {
    final sentToken = _token;
    try {
      return await _read(sentToken);
    } on Unauthorized {
      // A concurrent request may already have refreshed this token.
      final token = _token != sentToken ? _token : await _freshToken();
      // Outside the catch's try: another 401 propagates, never recurses.
      return await _read(token);
    }
  }
}
```

For a Dio adapter, use its documented request headers and `DioException` response status; retain the bounded retry behavior above. [Dio documentation](https://pub.dev/packages/dio).

## Golden tests and batch verification

Goldens are optional candidate regression checks, not original-app parity evidence. Use them when stable widgets and reviewed baselines make them cheaper than repeated emulator captures. Pin fonts, locale, surface size, pixel ratio and rendering environment; register teardown for changed test-view settings. Avoid unbounded `pumpAndSettle` on continuously animated screens.

Complete related fixes in the current phase, then run affected analyzer/tests/goldens as one batch and recapture affected emulator states together. Finish a lone remaining fix and check it directly. Run an earlier focused check when its result is needed for the next edit or a failure blocks progress. Do not update all goldens to dismiss an unexplained difference; update only reviewed affected baselines. Run required project checks before phase readiness.

Before accepting a journey, perform required cold-start/restart checks and compare a fresh installed build. If a development capture follows hot reload, record loaded source hashes and runtime session separately from the unchanged installed APK hash.

## Extracted assets

Android VectorDrawable XML is not SVG. Convert relevant paths to SVG or reproduce them with a `CustomPainter`, then compare viewBox, stroke, fill and scaling against the original. An inventory XML filename is only a drawable candidate; shapes/selectors are not necessarily vectors. Preserve nine-patch behavior, crop and font weights. Keep the asset used by the app and its provenance mapping; intermediate conversions belong in temporary storage.
