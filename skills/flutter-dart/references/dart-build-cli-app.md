---
name: dart-build-cli-app
description: >-
  Architectural patterns, entrypoint structure, exit codes, stream routing, and subprocess spawning for Dart command-line interface (CLI) applications. Use when building CLI tools, console utilities, scripts, argument parsing with `package:args` (ArgParser or CommandRunner), handling exit codes, configuring executables in pubspec.yaml, spawning Dart subprocesses, or compiling native CLI binaries. Don't use for Flutter UI widgets, web applications, or standalone HTTP backend servers.
---

# Building Dart CLI Applications

## Contents
* [1. Core Architecture & Process Lifecycle](#1-core-architecture--process-lifecycle)
* [2. Streams, Diagnostics & Formatting](#2-streams-diagnostics--formatting)
* [3. Project Configuration & Packaging](#3-project-configuration--packaging)
* [4. Argument Parsing & Command Routing](#4-argument-parsing--command-routing)
* [5. Native Async & Modern Stack Traces](#5-native-async--modern-stack-traces)
* [6. Subprocess Spawning & AOT Resilience](#6-subprocess-spawning--aot-resilience)
* [7. Signal Handling & Terminal Teardown](#7-signal-handling--terminal-teardown)
* [8. Testing CLI Applications](#8-testing-cli-applications)
* [9. Modern Compilation & Distribution](#9-modern-compilation--distribution)
* [10. Workflows & Audit Checklist](#10-workflows--audit-checklist)
* [References & Examples](#references--examples)

---

## 1. Core Architecture & Process Lifecycle

### Avoid Destructive Exits (`exit(N)`)
Calling `dart:io`'s `exit(int code)` invokes `Platform::Exit(code)` in the C++ runtime. It immediately terminates the OS process without unwinding the Dart stack:
* **Debugger Disconnect**: When launched with `--pause-isolates-on-exit`, the VM Service pauses isolates before shutdown to allow IDE inspection. `exit()` terminates the OS process before the VM Service can pause or inspect state.
* **Coverage Loss**: `package:coverage` queries execution lines over VM Service RPCs during the paused-on-exit state. `exit()` destroys the process before RPC extraction, yielding 0% coverage.
* **Buffer Truncation**: `stdout` and `stderr` are buffered asynchronous `IOSink` streams. `exit()` drops unflushed bytes.
* **Resource Leaks**: `finally` blocks (closing locks, deleting temp directories) are bypassed.

**Rule**: Avoid calling `exit(code)` directly during normal execution; set `exitCode = code` or return an integer exit code from `CommandRunner<int>` (from `package:args`) and allow the asynchronous `main()` function to return naturally. Do not call `exit()` on unhandled errors; throw an unhandled `Error` or exception so the runtime unwinds cleanly and exits with a non-zero status.

Standard POSIX exit codes (`/usr/include/sysexits.h`):
* `0`: Success (`EX_OK` / `ExitCode.success.code`)
* `64`: Command-line usage error (`EX_USAGE` / `ExitCode.usage.code`)
* `65`: Data format error (`EX_DATAERR` / `ExitCode.data.code`)
* `70`: Internal software crash (`EX_SOFTWARE` / `ExitCode.software.code`)
* `78`: Configuration error (`EX_CONFIG` / `ExitCode.config.code`)

*Note*: Prefer importing `package:io/io.dart` and using `ExitCode` constants
(e.g., `ExitCode.usage.code`, `ExitCode.software.code`) rather than magic
integer literals. For minimal standalone scripts without package dependencies,
standard POSIX integer literals (`0`, `64`, `70`) may be used.

```dart
import 'dart:io';
import 'package:args/command_runner.dart';
import 'package:io/io.dart' show ExitCode; // Provides standard POSIX ExitCode constants

Future<void> main(List<String> args) async {
  final runner = CommandRunner<int>('tool', 'CLI tool description.');
  try {
    final status = await runner.run(args);
    exitCode = status ?? ExitCode.success.code;
  } on UsageException catch (e) {
    stderr
      ..writeln(e.message)
      ..writeln(e.usage);
    exitCode = ExitCode.usage.code;
  }
}
```

### The Thin Entrypoint Pattern (`bin/` vs. `lib/src/`)
Keep `bin/*.dart` files strictly as minimal entrypoint trampolines (instantiate runner, pass `args`, await exit code). Place all command definitions, argument parsers, formatters, and business logic inside `lib/src/`.

* **Rationale**: Code in `bin/` cannot be cleanly imported via `package:` URIs. Moving logic into `lib/src/` allows the entire command runner, subcommand hierarchy, and business logic to be unit-tested in-memory in milliseconds (`< 2ms`) without spawning OS subprocesses.

```dart
// bin/my_cli.dart — Thin entrypoint trampoline
import 'dart:io';
import 'package:my_cli/src/cli.dart';

Future<void> main(List<String> args) async {
  exitCode = await runCli(args);
}
```

---

## 2. Output, Diagnostics & Formatting

* **Data vs. Diagnostics**: Write intended program results and machine-readable data exclusively to `stdout`. Write warnings, error messages, and debug logs exclusively to `stderr`.
* **The Error Usage Rule**: When an argument parsing or mandatory option error
  occurs (`FormatException`, `UsageException`, or `ArgumentError` thrown when
  accessing a missing `mandatory: true` option via `results.option(...)`), **both
  the error message and the usage text must write to `stderr`**, and exit code
  `64` (`EX_USAGE` / `ExitCode.usage.code`) must be returned. `stdout` should
  ONLY receive usage help when the user explicitly requests it via `--help` or
  `-h`.
* **No `print()` in Error Handlers**: `print()` routes to `stdout`. Use `stderr.writeln()` for all failure notifications. For standard output, prefer `stdout.writeln()` over `print()` to comply with the [`avoid_print`](https://dart.dev/tools/linter-rules/avoid_print) lint rule (unless `analysis_options.yaml` explicitly configures `avoid_print: false`).
* **Terminal Capability Detection & `NO_COLOR`**: Verify `stdout.hasTerminal`, `stdout.supportsAnsiEscapes`, and `!Platform.environment.containsKey('NO_COLOR')` before emitting ANSI color or cursor escape codes:
  ```dart
  bool get useAnsi =>
      stdout.hasTerminal &&
      stdout.supportsAnsiEscapes &&
      !Platform.environment.containsKey('NO_COLOR');
  ```
* **Machine-Readable Modes**: When `--json` or `--machine` flags are passed, format data as JSON to `stdout` and route logs to `stderr`.

---

## 3. Project Configuration & Packaging

### Scaffolding & Pubspec Executable Mapping (`executables:`)
Scaffold new command-line projects using `dart create -t console <package_name>`, which initializes the standard `bin/` and `lib/` layout. Always declare executables in `pubspec.yaml` under `executables:` to map command names to scripts in `bin/`, enabling clean invocation via `dart run <command>` (without specifying `bin/...dart`) and configuring global binary symlinks for `dart install`:

```yaml
name: my_cli
description: High-performance CLI tool.
version: 1.0.0

executables:
  my_cli: # Maps to bin/my_cli.dart
  secondary_cmd: helper # Maps to bin/helper.dart
```

### Single-Source Versioning (`package:build_version`)
Avoid hardcoding `--version` strings in `bin/*.dart` or manually synchronizing constant files. Use `package:build_version` to generate `lib/src/version.dart` containing `const packageVersion = 'x.y.z';` directly from `pubspec.yaml` during builds.

### Caching Conventions
Store transient cache files in `.dart_tool/<package_name>/`. Never write persistent cache files directly to the project root.

---

## 4. Argument Parsing & Command Routing

Import `package:args` to manage command-line arguments:

* **Simple Scripts**: Use `ArgParser` directly with `addFlag()` and `addOption()`.
* **Multi-Command Tools**: Implement `CommandRunner<int>` and extend `Command<int>` for each subcommand, returning POSIX exit codes directly.
* **Type-Safe Accessors**: Use `results.flag('name')`, `results.option('name')`, and `results.multiOption('name')` (available in `package:args` 2.5+) instead of map indexing `operator []` to eliminate manual type casts (`as bool`, `as String?`).
* **Complex Options Models**: For applications with extensive flags, use `package:build_cli` to generate strongly-typed options classes. Leverage named default overrides (e.g. `{String? hostDefaultOverride}`) to cleanly merge configuration files with CLI flags.

---

## 5. Native Async & Modern Stack Traces

* **Avoid `Chain.capture()`**: The Dart VM natively preserves asynchronous stack frames across `await` suspension points. `Chain.capture` wraps the event loop in custom Zones, incurring substantial allocation overhead and trapping errors across Zone boundaries.
* **Sanitize with `Trace.from(st).terse`**: Use static utilities from `package:stack_trace` on uncaught errors without capturing zones:

```dart
import 'dart:io';
import 'package:io/io.dart' show ExitCode;
import 'package:stack_trace/stack_trace.dart';

Future<void> runMain(List<String> args) async {
  try {
    await executeLogic(args);
    exitCode = ExitCode.success.code;
  } catch (e, st) {
    stderr.writeln('Fatal error: $e');
    if (args.contains('-v') || args.contains('--verbose')) {
      stderr.writeln(Trace.from(st).terse);
    }
    exitCode = ExitCode.software.code;
  }
}
```

---

## 6. Subprocess Spawning & AOT Resilience

When spawning Dart SDK subprocesses or executing other Dart tools (e.g., `dart format`, `dart test`, `build_runner`):

* **Do not assume `Platform.resolvedExecutable` or `Platform.executable` points to the `dart` command-line executable**: In standalone AOT-compiled binaries (`dart install` / `dart compile exe`), `resolvedExecutable` points to the compiled application binary itself, causing recursive self-invocation loops or flag rejection crashes.
* **Use `package:cli_util`**: Resolve the Dart SDK executable using `cli_util.dartExecutable` or `cli_util.sdkPath` instead of writing custom PATH or directory scrapers.
* See version requirements and detailed technical guide in [references/aot_sdk_discovery.md](references/aot_sdk_discovery.md).

---

## 7. Signal Handling & Terminal Teardown

If your CLI alters terminal modes, displays spinners, or opens listening sockets:

* **Windows Signal Guard**: On Windows, `ProcessSignal.sigterm.watch()` throws `UnsupportedError`. Guard `sigterm` with `if (!Platform.isWindows)`.
* **Echo & Line Mode Teardown**: If setting `stdin.echoMode = false` or `stdin.lineMode = false`, check `if (!stdin.hasTerminal) return;` first, and install a `SIGINT` listener and `finally` block to restore them so user keystrokes remain visible after exit.
* **Cursor Visibility**: If emitting ANSI hide-cursor (`\x1B[?25l`), always restore cursor visibility (`\x1B[?25h`) on exit or cancellation.
* **Socket Cleanup**: Explicitly close listening `HttpServer` or `ServerSocket` instances (`server.close(force: true)`) on termination signals to immediately release OS ports.
* See detailed patterns in [references/signals_and_terminal.md](references/signals_and_terminal.md).

---

## 8. Testing CLI Applications

Structure testing across two distinct layers:

1. **Unit Tests (In-Memory, `< 5ms`)**: Test command classes, option parsing, and business logic directly by importing `package:<pkg>/src/...` in `test/`.
2. **Integration Tests (Subprocesses)**: Use `package:test_process` and `package:test_descriptor` to verify end-to-end binary execution, process I/O streaming, and OS exit codes:

```dart
import 'package:test/test.dart';
import 'package:test_descriptor/test_descriptor.dart' as d;
import 'package:test_process/test_process.dart';

void main() {
  test('CLI processes input and exits cleanly', () async {
    await d.file('input.txt', 'hello').create();

    final process = await TestProcess.start('dart', [
      'run',
      'bin/my_cli.dart',
      '--input',
      d.path('input.txt'),
    ]);

    await expectLater(process.stdout, emitsThrough('Processing complete.'));
    await process.shouldExit(0);
  });
}
```

---

## 9. Modern Compilation & Distribution

Dart 3.12+ standardizes CLI distribution around `dart run` and `dart install` (moving away from `dart pub global activate`):

* **Ephemeral Execution (JIT)**: `dart run <package>@<version> [args]` downloads and runs the CLI on demand.
* **Global Installation (Native AOT)**: `dart install <package>` compiles the package entrypoint to a fast native standalone binary in `~/.dart/install/bin/`.
* **Local Development**: Use `dart run <command>` (resolves via `executables:` in `pubspec.yaml`) or `dart run bin/cli.dart`.
* **Bundling Dynamic Libraries & Code Assets**: Use `dart build cli`. Outputs bundle to `build/cli/_/bundle/`.
* **Standalone Executable Compilation**: Use `dart compile exe bin/cli.dart -o <output_path>`.

---

## 10. Workflows & Audit Checklist

### Implementation Workflow
- [ ] Declare entry points in `pubspec.yaml` under `executables:`.
- [ ] Keep `bin/*.dart` as a thin entrypoint; place command logic in `lib/src/`.
- [ ] Return integer exit codes or set `exitCode = N`; avoid raw `exit(N)`.
- [ ] Direct errors, warnings, and usage on parse failure to `stderr`.
- [ ] Use `results.flag()`, `results.option()`, and `results.multiOption()` for type safety.
- [ ] Validate `useAnsi` (checking `stdout.hasTerminal`, `supportsAnsiEscapes`, and `NO_COLOR`) before emitting ANSI codes.
- [ ] Spawn child tools using `cli_util.dartExecutable`, never `Platform.resolvedExecutable`.
- [ ] Unit-test command runners in-memory; test end-to-end binary execution with `test_process`.

---

## References & Examples

* **Single-Command Tool Template**: [examples/single_command_tool.dart](examples/single_command_tool.dart)
* **Multi-Command Runner Template**: [examples/multi_command_runner.dart](examples/multi_command_runner.dart)
* **AOT SDK Discovery & Subprocess Spawning**: [references/aot_sdk_discovery.md](references/aot_sdk_discovery.md)
* **Signal Handling & Terminal Teardown**: [references/signals_and_terminal.md](references/signals_and_terminal.md)


---

> Appendix vendored from upstream `skills/dart-build-cli-app/references/` (flutter/agent-plugins @ 0ef3972) — kept alongside the guide because this skill uses a flat references layout.

# Dart SDK Discovery and Subprocess Spawning in AOT & JIT

Guidance on locating the Dart SDK and spawning Dart child processes across JIT (`dart run`, `pub global activate`) and standalone AOT (`dart compile exe`, `dart install`) execution modes.

---

## 1. The AOT SDK Discovery Trap

When writing CLI developer tools that spawn `dart` child processes (e.g. running `build_runner`, `dart format`, `dart test`, or code analyzers), developers frequently write:

```dart
// ❌ WRONG: Breaks when compiled to AOT
final dart = Platform.resolvedExecutable;
final sdkDir = path.dirname(path.dirname(dart));
```

### Why This Fails in Standalone AOT:
* **JIT VM (`dart run`, `pub global activate`)**: `Platform.resolvedExecutable` points directly to `<dart-sdk>/bin/dart`. Calling `dirname(dirname(...))` resolves to the valid SDK root directory.
* **AOT Binary (`dart compile exe`, `dart install`)**: `Platform.resolvedExecutable` points to the compiled application binary (e.g. `~/.dart/install/app-bundles/my_cli/.../bin/my_cli`).

### Consequences of Naive Resolution:
1. **Recursive Subprocess Loop**: If the application executes `Platform.resolvedExecutable` expecting the `dart` VM, it spawns itself recursively.
2. **Flag Rejection Crash**: If the child process passes VM flags (such as `--observe`, `--enable-vm-service`) or tool subcommands (like `run`, `format`, or `test`), the compiled binary fails immediately with unknown option errors.
3. **Broken SDK Root**: Traversing parent directories from `Platform.resolvedExecutable` to locate SDK resources (such as `libraries.json`) fails because the binary resides in an application bundle directory rather than a Dart SDK installation.

---

## 2. The Solution: `package:cli_util` (`^0.6.0`)

Do not write bespoke SDK discovery probes. Depend on `package:cli_util` (version 0.6.0 or higher), which provides memoized, nullable getters (`dartExecutable` and `sdkPath`) that locate the Dart SDK across both JIT and AOT environments:

```dart
import 'dart:io' as io;
import 'package:cli_util/cli_util.dart' as cli_util;

Future<void> runSubprocess() async {
  // Resolves the dart executable across both JIT and AOT environments
  final dartExe = cli_util.dartExecutable;
  if (dartExe == null) {
    io.stderr.writeln('Error: Could not locate the Dart SDK on PATH.');
    io.exitCode = 1;
    return;
  }

  final result = await io.Process.run(dartExe, ['format', '.']);
  io.stdout.write(result.stdout);
  io.stderr.write(result.stderr);
}
```

### Potential Dart SDK Locations:
A valid Dart SDK and `dart` executable may reside in several environmental locations across different developer setups:
* **Running VM (`Platform.resolvedExecutable`)**: When running on the JIT VM (`dart run`), `resolvedExecutable` points directly to `<dart-sdk>/bin/dart`.
* **Explicit Environment (`DART_SDK`)**: Defined when a developer explicitly points `DART_SDK` to an SDK installation directory.
* **System `PATH`**: Resolved via system `PATH` entries (`dart`, `dart.exe`, or `dart.bat`), including dereferencing symlinks and checking `bin/cache/dart-sdk` for Flutter installations.
* **Flutter Root (`FLUTTER_ROOT`)**: Bundled under `FLUTTER_ROOT/bin/cache/dart-sdk`.

The exact search order and SDK directory validation logic should be delegated to `package:cli_util` rather than re-implemented in application code.

---

## 3. Subprocess Spawning Invariants

When executing child subprocesses from a Dart CLI:

1. **Always use `cli_util.dartExecutable`**: Never pass `Platform.executable` or `Platform.resolvedExecutable`.
2. **Fallback to `'dart'` on `PATH`**: If `package:cli_util` is not an option, execute the literal string `'dart'` directly via `Process.start('dart', [...], runInShell: Platform.isWindows)`.
3. **Windows Batch File Handling**: On Windows, Flutter installs `dart.bat` in `flutter/bin`. Invoking batch files directly via `Process.start` requires `runInShell: true` unless pointing to the resolved binary `dart.exe`.


---

# Signal Handling, Terminal Teardown, and Stream Resilience

Guidance on cross-platform signal listeners, restoring terminal modes, tearing down network resources, and handling broken pipes in Dart CLI applications.

---

## 1. Cross-Platform Signal Handling

Standard POSIX signals (`SIGINT`, `SIGTERM`) require platform-specific guards because Windows does not implement POSIX `SIGTERM`.

### The Windows `SIGTERM` Guard Rule:
Calling `ProcessSignal.sigterm.watch()` on Windows throws an unhandled `UnsupportedError`. Multi-platform signal handlers must always guard `sigterm`:

```dart
import 'dart:async';
import 'dart:io';
import 'package:async/async.dart';

/// Listens for process termination signals across Windows, macOS, and Linux.
Stream<ProcessSignal> watchTerminationSignals() {
  if (Platform.isWindows) {
    return ProcessSignal.sigint.watch();
  }
  return StreamGroup.merge([
    ProcessSignal.sigint.watch(),
    ProcessSignal.sigterm.watch(),
  ]);
}
```

---

## 2. Terminal Mode & Cursor Restoration

If your CLI mutates the terminal state (e.g., interactive menus, password input prompts, progress spinners):

### A. Raw Mode Teardown (`echoMode` & `lineMode`):
If setting `stdin.echoMode = false` or `stdin.lineMode = false`, install a signal handler to restore them upon user cancellation (`Ctrl+C` / `SIGINT`). Otherwise, the host shell remains in raw mode and user keystrokes become invisible after exit.

```dart
import 'dart:io';

void enableInteractiveMode() {
  // Defensive guard: only configure terminal modes if standard input is an interactive TTY.
  if (!stdin.hasTerminal) return;
  stdin.echoMode = false;
  stdin.lineMode = false;

  // Ensure terminal state is synchronously restored on Ctrl+C.
  final sub = ProcessSignal.sigint.watch().listen((_) {
    restoreTerminal();
    // Exiting with 128 + SIGINT (2) = 130 is the standard POSIX protocol
    // for asynchronous signal handlers to communicate signal interruption to the host shell.
    exit(130);
  });

  try {
    // Run interactive loop...
  } finally {
    sub.cancel();
    restoreTerminal();
  }
}

void restoreTerminal() {
  if (stdin.hasTerminal) {
    stdin.lineMode = true;
    stdin.echoMode = true;
  }
}
```

### B. Cursor Visibility (Spinners & Progress Bars):
If emitting ANSI escape code to hide the cursor (`\x1B[?25l`), always restore cursor visibility (`\x1B[?25h`) inside `finally` blocks and signal handlers:

```dart
void showCursor() {
  if (useAnsi) {
    stdout.write('\x1B[?25h');
  }
}

/// Canonical ANSI support check respecting NO_COLOR standards.
bool get useAnsi =>
    stdout.hasTerminal &&
    stdout.supportsAnsiEscapes &&
    !Platform.environment.containsKey('NO_COLOR');
```

---

## 3. Server Socket & Child Process Teardown

* **Listening Sockets**: If the CLI starts an `HttpServer` or TCP `ServerSocket`, listen for termination signals to close the socket immediately (`server.close(force: true)`) so the OS releases port bindings without waiting for kernel socket timeouts.
* **Child Processes**: When spawning long-running child processes, register a termination listener to forward signals (`childProcess.kill(ProcessSignal.sigterm)`) before the parent exits to prevent orphaned background processes.

---

## 4. Broken Pipe (`EPIPE` / `SocketException`) Handling

When piping CLI output to downstream commands that terminate early (e.g., `my_cli | head -n 5` or `my_cli | grep -q foo`), the downstream process closes the pipe. Subsequent writes to `stdout` throw `SocketException: Broken pipe (errno = 32)`.

Intercept broken pipe exceptions without printing noisy crash traces to `stderr`:

```dart
import 'dart:io';

Future<void> safeWriteln(String line) async {
  try {
    stdout.writeln(line);
  } on SocketException catch (e) {
    // EPIPE / Broken pipe: downstream closed standard input.
    if (e.osError?.errorCode == 32 || e.message.contains('Broken pipe')) {
      await stdout.close().catchError((_) {});
      // In a bulk streaming context, calling exit(0) immediately stops the
      // producer loop when downstream has closed its pipe.
      exit(0);
    }
    rethrow;
  }
}
```
