# Writing the Flutter code

Use the existing architecture and [flutter-stack.md](flutter-stack.md) for dependency choices. Implement observed behavior; no state wrapper automatically fixes networking, ordering and persistence bugs.

## Convert capture pixels to logical dimensions

On Android, `capture_dpr = density_dpi / 160` and `logical_px = physical_px / capture_dpr`. Read density from the capture's environment, not the rendering device. For iOS, use the recorded capture scale, not the Android dpi formula. A resized screenshot cannot provide trustworthy native measurements.

At 420 dpi, a 132 px button is `132 / 2.625 = 50.28` logical pixels. Confirm any rounding against the original. Convert once during measurement; do not put runtime device-pixel-ratio corrections into layout constants.

Glyph height is not `fontSize`: font metrics, line height and text scaling intervene. Use extracted fonts and confirm text at matching scale. Keep safe-area insets separate from content padding.

## Reuse confirmed tokens

Reuse the project's token file. When repeated measurements justify automation, run `theme_extract.py` on representative captures of the same theme and density:

```bash
python3 "$DITTO_SKILL/scripts/theme_extract.py" \
  evidence/runtime/*/*/original/*/screen.png \
  --hierarchy evidence/runtime/*/*/original/*/hierarchy.xml \
  --dpi 420 --dart lib/design/tokens.dart
```

Supply actual paths; omit `--hierarchy` when unavailable. Write `--json` only for a consumer that needs it, rather than maintaining a duplicate token record. This tool clusters colours and selects observed pixel colours as representatives. It suggests roles and nearest-neighbour gaps across hierarchy bounds, not declared theme values or guaranteed sibling spacing. Exclude photographs/system UI from interpretation, separate dark/light themes, and verify generated values before using them. PNG compression is lossless; blending and source images can still affect rendered colours.

Use confirmed values in `ThemeData` and explicit `ColorScheme` roles. A generated seed palette can differ from the original even when its seed matches. Update tokens only when new evidence changes them; do not rerun extraction after every screenshot.

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

Complete related fixes in the current phase, then run affected analyzer/tests/goldens as one batch and recapture affected emulator states together. Finish a lone remaining fix and check it directly. Run an earlier focused check when its result is needed for the next edit or a failure blocks progress. Do not update all goldens to dismiss an unexplained difference; update only reviewed affected baselines. Run required project checks at the journey checkpoint.

Before accepting a journey, perform required cold-start/restart checks and compare a fresh installed build. If a development capture follows hot reload, record loaded source hashes and runtime session separately from the unchanged installed APK hash.

## Extracted assets

Android VectorDrawable XML is not SVG. Convert relevant paths to SVG or reproduce them with a `CustomPainter`, then compare viewBox, stroke, fill and scaling against the original. An inventory XML filename is only a drawable candidate; shapes/selectors are not necessarily vectors. Preserve nine-patch behavior, crop and font weights. Keep the asset used by the app and its provenance mapping; intermediate conversions belong in temporary storage.
