# Flutter implementation stack

Primary package documentation checked 2026-09-14. The choices below are Ditto's defaults for a new app with networked features; they are not a requirement to replace an existing architecture. Retain an existing working Bloc, Provider, HTTP client, or database unless it prevents a demonstrated behavior requirement. For how to write against this stack — state patterns, the px→dp conversion, golden tests — see [flutter-build.md](flutter-build.md).

## Library selection

| Concern | Default / add when | Concrete rule and source |
| --- | --- | --- |
| Async feature state | `flutter_riverpod` | Use providers for injected repositories and async feature controllers. Preserve loading, cached-data, refreshing, and error states separately when observed. Checked package: 3.4.3; do not copy Riverpod 2.x examples blindly. [Package](https://pub.dev/packages/flutter_riverpod) |
| HTTP | `dio` | Use a shared configured client behind a service/repository for cancellation, interceptors, multipart, and timeout control. Reproduce refresh/retry behavior explicitly; do not retry writes without the observed idempotency contract. Checked: 5.11.1. [Package](https://pub.dev/packages/dio) |
| Routing | `go_router` | Use for deep links, redirects and nested tab navigation; test system back and restored tab stacks. A tiny app may keep Navigator. Checked: 18.0.1. [Package](https://pub.dev/packages/go_router) |
| Relational/offline data | `drift` + `drift_flutter` | Use for durable entities, transactions, observed offline queues, migrations, and reactive queries. Add `drift_dev` and `build_runner` as dev dependencies. Checked Drift: 2.35.0. [Package](https://pub.dev/packages/drift), [setup](https://drift.simonbinder.eu/setup/) |
| Simple preferences | `shared_preferences` | Theme/onboarding/noncritical settings only. Choose its async/cache API deliberately when multiple isolates or native code write values. Do not use it for critical records or sessions. [Package](https://pub.dev/packages/shared_preferences) |
| Session secrets | `flutter_secure_storage` | Use platform secure storage for tokens requiring protected persistence. Verify Android backup/migration and iOS Keychain accessibility configuration against restart/logout requirements. Do not copy raw captured credentials into code. [Package](https://pub.dev/packages/flutter_secure_storage) |
| JSON DTOs | `json_annotation` + dev `json_serializable`, `build_runner` | Generate wire serialization when models justify it. Preserve absent vs null, field names, enums, numeric precision, and error bodies. Generators do not infer an API contract from a response sample. [Package](https://pub.dev/packages/json_serializable) |
| Immutable unions/copying | `freezed_annotation` + dev `freezed` | Optional when feature state has meaningful variants or model copying; do not add code generation for two trivial values. Use the resolved major's class syntax. [Package](https://pub.dev/packages/freezed) |
| Remote image caching | `cached_network_image` | Add when placeholders, error images, and disk caching match the observed feature. Verify cache keys, expiry, auth headers, and logout invalidation. Checked: 4.0.0. [Package](https://pub.dev/packages/cached_network_image) |
| SVG assets | `flutter_svg` | Use for actual SVGs. Android VectorDrawable XML is not SVG: convert or reproduce its paths and verify the result. [Package](https://pub.dev/packages/flutter_svg) |
| Typed native bridge | dev `pigeon` | Generate Dart/Kotlin/Swift message contracts for retained native behavior. Keep generated sides on the same generator version. Prefer an existing plugin when it matches; use FFI for a suitable C ABI. [Package](https://pub.dev/packages/pigeon) |
| OS interactions in tests | dev `patrol` + `patrol_cli` | Candidate-side testing for permissions, notifications and other native UI. Complete native setup before running; Patrol cannot simply attach its Dart tests to an arbitrary original APK. [Package](https://pub.dev/packages/patrol) |

Do not automatically add Firebase, a maps SDK, payments, Bluetooth, or a background-task plugin because they appeared in the research's example app. Identify the observed capability and platform requirements first, then verify a specific package. SDK configuration and permitted test endpoints must be supplied or obtained from the user's project.

## Resolve dependencies rather than paste a stale pubspec

Choose the smallest sufficient stack. Local widget state can stay local; simple navigation can use Navigator. Keep an existing HTTP client. For a new small HTTP surface, consider `package:http`; choose Dio when its interceptors, cancellation or upload facilities remove work you actually need. Add Drift for relational/durable requirements, not a few preferences. Package capabilities and SDK constraints matter more than publication date. [HTTP package](https://pub.dev/packages/http).

Reduce handwritten code, not readability. Reuse widgets, repository operations and platform plugins before writing wrappers. Extract shared code when repeated behavior is established; avoid a generic framework for one screen. Keep generated code out of routine model context: edit generator inputs, run generation once after related model changes, and inspect diagnostics or relevant generated sections only when necessary. Commit generated outputs according to the project's existing policy; context exclusion does not mean deletion.

Use `json_serializable` for recurring wire models where field mappings and conversion boilerplate justify it. Add Freezed for meaningful immutable unions/copying needs; plain Dart classes, records or sealed classes may suffice for small models. Riverpod generation is optional: retain the project's approach and account for generator setup/build time. Do not install code generation solely to shorten a trivial provider. [Riverpod code generation](https://riverpod.dev/docs/concepts/about_code_generation).

Inside the target Flutter project, record `flutter --version`, `dart --version`, and existing constraints. Run only the applicable groups:

```bash
# Run only the individual additions justified by the active feature:
flutter pub add flutter_riverpod  # shared async feature state
flutter pub add dio              # richer HTTP requirements
flutter pub add go_router        # declarative routing/deep links

# Relational persistence:
flutter pub add drift drift_flutter path_provider
flutter pub add --dev drift_dev build_runner

# JSON models:
flutter pub add json_annotation
flutter pub add --dev json_serializable build_runner

# Optional union models:
flutter pub add freezed_annotation
flutter pub add --dev freezed
```

Resolve, inspect `pubspec.lock`, and commit the application lockfile. Record selected versions in the existing toolchain record (or a compact section of `spec/app.md`); avoid duplicating the lockfile. The versions above are a research snapshot, not a tested combination for the user's SDK. Do not upgrade an existing project just to match them. Consult current primary docs when adding/upgrading a dependency or resolving an API uncertainty; reuse the finding for the same locked version. After related generator-input edits, run `dart run build_runner build` once; inspect collisions instead of blindly deleting conflicting outputs.

## Implement a vertical feature

Use this structure only for a new project; map it to existing conventions otherwise:

```text
lib/
  app/                   router, application setup
  core/                  network, database, secure-storage adapters
  design/                tokens.dart (see flutter-build.md), theme.dart
  features/<feature>/
    data/                wire DTOs, service, repository implementation
    application/         feature controller and state transitions
    presentation/        screen and reusable feature widgets
```

Start with the observed input/output contract, not a directory scaffold. Inject the repository so the same screen/controller can run against sanitized fixtures and the permitted live backend. Fixture mode must be explicit; a mocked successful checkout is not live checkout parity.

Map screen transitions to explicit controller events and states — see [flutter-build.md](flutter-build.md#async-state-and-durable-effects) for separate ordering, submission, refresh, authentication and durability contracts. Implement only semantics supported by evidence or an explicitly chosen product change.

For assets, retain an asset map from extracted path/hash to target path, logical size, density/scale and font weight. Reuse confirmed tokens; optionally use `scripts/theme_extract.py` when repeated measurement warrants it ([flutter-build.md](flutter-build.md#reuse-confirmed-tokens)). Use local font files when available. Preserve image fit/crop, SVG/viewBox geometry, Android nine-patch stretch behavior, and measured icon bounds. Compare at matched text scale and density before changing layout to fix a screenshot.

For native features, document the Dart call/event, Kotlin/Swift implementation, permission prerequisite, lifecycle, cancellation/error result, and parity test. Do not force a platform feature into Dart when a small native adapter produces the required behavior.

## Build and test commands

After the related edits are complete, run applicable checks together from the implementation root; do not run this entire sequence after each small correction:

```bash
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test                                    # includes golden tests, see flutter-build.md
flutter build apk --debug
```

Adapt existing paths and flavors. After launching a supported device, run `flutter test integration_test -d "$CANDIDATE_DEVICE"` when those tests exist. On macOS, `flutter build ios --simulator` validates a simulator build only; it is not proof of signing or physical-device behavior. Run tests for each required target rather than implying Android results cover iOS. Flutter's integration layer and system-UI limitations are documented in [Flutter integration tests](https://docs.flutter.dev/testing/integration-tests).
