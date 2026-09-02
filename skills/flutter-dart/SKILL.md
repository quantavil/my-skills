---
name: flutter-dart
description: Master skill for Dart and Flutter development. Covers architecture best practices, UI and responsive layouts, layout debugging (RenderFlex overflow), declarative routing (go_router), localization (l10n/i18n), REST API integration (http), JSON serialization, unit/widget/integration testing (package:test, WidgetTester, package:checks, mockito), static analysis, runtime error debugging, FFI and native assets (ffigen, hooks), CLI apps, and documentation.
---

# Dart & Flutter Development Master Skill

Comprehensive guide and playbook collection for developing Dart and Flutter applications.

## Attribution & Credits

> [!NOTE]
> The reference guides in this skill are adapted and curated from the official [flutter/agent-plugins](https://github.com/flutter/agent-plugins) repository created and maintained by the **Flutter team at Google**. All credit for the underlying workflows and domain best practices goes to the original authors.

---

## Agent Usage Instructions

When addressing a Dart or Flutter task:
1. Consult the **Routing Table** below to identify the specific guide covering your task.
2. Load the corresponding reference markdown file from `skills/flutter-dart/references/` using `view_file`.
3. Follow the detailed steps, checklists, and code patterns provided in that reference guide.

---

## Reference Routing Table

### 1. Architecture & Core Application Design
| Topic | Reference File | Use When |
| :--- | :--- | :--- |
| **Layered Architecture** | [`references/flutter-apply-architecture-best-practices.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/flutter-apply-architecture-best-practices.md) | Architecting Flutter apps with clean layered boundaries (UI, Logic/State, Data/Services). |
| **Declarative Routing** | [`references/flutter-setup-declarative-routing.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/flutter-setup-declarative-routing.md) | Configuring URL-based navigation with `go_router`, deep links, and route guards. |
| **Localization (l10n/i18n)** | [`references/flutter-setup-localization.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/flutter-setup-localization.md) | Setting up `flutter_localizations`, `intl`, `l10n.yaml`, and `.arb` files for multi-language support. |
| **HTTP & REST APIs** | [`references/flutter-use-http-package.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/flutter-use-http-package.md) | Making GET, POST, PUT, DELETE requests using `package:http`. |
| **JSON Serialization** | [`references/flutter-implement-json-serialization.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/flutter-implement-json-serialization.md) | Writing type-safe `fromJson` and `toJson` serialization models with `dart:convert`. |
| **CLI Applications** | [`references/dart-build-cli-app.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-build-cli-app.md) | Building Dart command-line tools, handling arguments, exit codes, and cross-platform scripts. |

### 2. UI, Layout & Component Development
| Topic | Reference File | Use When |
| :--- | :--- | :--- |
| **Responsive Layouts** | [`references/flutter-build-responsive-layout.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/flutter-build-responsive-layout.md) | Building adaptive UIs for mobile, tablet, and desktop using `LayoutBuilder`, `MediaQuery`, and `Expanded`. |
| **Layout Issue Debugging** | [`references/flutter-fix-layout-issues.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/flutter-fix-layout-issues.md) | Fixing `RenderFlex overflowed`, unbounded height constraints, and viewport errors. |
| **Widget Previews** | [`references/flutter-add-widget-preview.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/flutter-add-widget-preview.md) | Creating interactive component previews using the `previews.dart` workflow. |

### 3. Testing & Quality Assurance
| Topic | Reference File | Use When |
| :--- | :--- | :--- |
| **Dart Unit Testing** | [`references/dart-add-unit-test.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-add-unit-test.md) | Writing and organizing unit tests for pure Dart functions, classes, and logic using `package:test`. |
| **Flutter Widget Testing** | [`references/flutter-add-widget-test.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/flutter-add-widget-test.md) | Writing component tests using `WidgetTester` to verify UI rendering and user interactions. |
| **Integration Testing** | [`references/flutter-add-integration-test.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/flutter-add-integration-test.md) | End-to-end integration tests using `package:integration_test` and Flutter Driver. |
| **Test Mocks Generation** | [`references/dart-generate-test-mocks.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-generate-test-mocks.md) | Generating mock objects with `package:mockito` and `build_runner`. |
| **Checks Package Migration** | [`references/dart-migrate-to-checks-package.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-migrate-to-checks-package.md) | Migrating matchers from `package:matcher` (`expect(a, equals(b))`) to `package:checks` (`check(a).equals(b)`). |
| **Code Coverage** | [`references/dart-collect-coverage.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-collect-coverage.md) | Collecting test coverage and generating LCOV reports. |

### 4. Debugging, Diagnostics & Modern Dart
| Topic | Reference File | Use When |
| :--- | :--- | :--- |
| **Runtime Errors & Hot Reload** | [`references/dart-fix-runtime-errors.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-fix-runtime-errors.md) | Diagnosing runtime exceptions from stack traces and verifying fixes via hot reload. |
| **Static Analysis & Lints** | [`references/dart-run-static-analysis.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-run-static-analysis.md) | Running `dart analyze` and automatically fixing lints with `dart fix --apply`. |
| **Package Dependency Conflicts** | [`references/dart-resolve-package-conflicts.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-resolve-package-conflicts.md) | Resolving version incompatibility errors during `pub get` or `flutter pub get`. |
| **Pattern Matching** | [`references/dart-use-pattern-matching.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-use-pattern-matching.md) | Writing idiomatic switch expressions, destructuring, and pattern matching. |
| **Primary Constructors** | [`references/dart-use-primary-constructors.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-use-primary-constructors.md) | Writing concise primary constructor syntax and initializer lists. |
| **API Documentation** | [`references/dart-write-documentation.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-write-documentation.md) | Writing Effective Dart `///` doc comments for libraries, classes, and members. |

### 5. Native Interop (FFI & Native Assets)
| Topic | Reference File | Use When |
| :--- | :--- | :--- |
| **FFI Bindings (`ffigen`)** | [`references/dart-use-ffigen.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-use-ffigen.md) | Auto-generating C / Objective-C / Swift FFI bindings with `package:ffigen`. |
| **Native Assets & Hooks** | [`references/dart-setup-ffi-assets.md`](file:///home/quantavil/Documents/Project/my-skills/skills/flutter-dart/references/dart-setup-ffi-assets.md) | Compiling and packaging C/C++ Code Assets using `hook/build.dart` and `package:native_toolchain_c`. |
