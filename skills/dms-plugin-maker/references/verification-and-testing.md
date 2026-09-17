# DMS Plugin Verification & Testing Rig

Every production-grade DMS plugin must ship with an automated, multi-phase verification test harness. This guarantees that logic bugs, QML syntax errors, and schema mismatches are caught before deployment.

---

## The Triple-Validation Suite

```
  ┌───────────────────────────────────────────────────────────┐
  │ 1. Engine Logic (Node.js)    node tests/test_engine.js     │
  ├───────────────────────────────────────────────────────────┤
  │ 2. QML Syntax (qmllint)      bash tests/test_qml_syntax.sh│
  ├───────────────────────────────────────────────────────────┤
  │ 3. Manifest (Schema Valid)   python3 tests/validate_man...│
  ├───────────────────────────────────────────────────────────┤
  │ 4. Live DMS Shell Reload     dms restart && dms ipc call  │
  └───────────────────────────────────────────────────────────┘
```

---

## 1. Phase 1: Pure Engine Unit Tests (`tests/test_engine.js`)

Because the calculation engine (`*Engine.js`) is pure JavaScript without UI dependencies, it runs directly in Node.js with built-in `node:assert`:

```javascript
// tests/test_engine.js
const assert = require('node:assert');
const Engine = require('../MyPluginEngine.js');

console.log("--- 1. Testing Core Calculations ---");
const initialState = { count: 0, active: false };
const next = Engine.increment(initialState);
assert.strictEqual(next.count, 1);
assert.strictEqual(next.active, true);

console.log("--- 2. Testing Boundary Conditions ---");
const wrapped = Engine.decrement({ count: 0 });
assert.strictEqual(wrapped.count, 0); // Clamped at 0

console.log("========================================");
console.log("ALL ENGINE UNIT TESTS PASSED");
console.log("========================================");
```

Run with:
```bash
node tests/test_engine.js
```

---

## 2. Phase 2: QML Syntax & Module Linting (`tests/test_qml_syntax.sh`)

Catches broken bindings, missing imports, unclosed brackets, and syntax errors using Qt's official `qmllint` compiler tool:

```bash
#!/usr/bin/env bash
set -eo pipefail

QMLLINT=""
for candidate in qmllint /usr/lib/qt6/bin/qmllint /usr/bin/qmllint; do
    if command -v "$candidate" >/dev/null 2>&1; then
        QMLLINT="$candidate"
        break
    fi
done

if [ -z "$QMLLINT" ]; then
    echo "Warning: qmllint not found, skipping linting phase."
    exit 0
fi

echo "=== Running QML Syntax Validation ==="
for file in *.qml; do
    [ -e "$file" ] || continue
    echo "Checking $file..."
    "$QMLLINT" "$file"
    echo "  ✔ $file syntax valid"
done
echo "=== All QML components passed syntax checks ==="
```

---

## 3. Phase 3: Manifest Schema Compliance (`tests/validate_manifest.py`)

Ensures `plugin.json` adheres strictly to DMS constraints and permissions:

```python
#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def validate():
    root = Path(__file__).resolve().parent.parent
    manifest = root / "plugin.json"
    if not manifest.exists():
        sys.exit("Error: plugin.json missing")

    with open(manifest) as f:
        data = json.load(f)

    # Required keys
    required = ["id", "name", "description", "version", "author", "type", "capabilities"]
    for k in required:
        if k not in data:
            sys.exit(f"Validation Error: Missing required field '{k}'")

    # Permissions check
    if data.get("settings") and "settings_write" not in data.get("permissions", []):
        sys.exit("Validation Error: Plugin declares 'settings' but lacks 'settings_write' permission")

    print("SUCCESS: plugin.json is strictly valid!")

if __name__ == "__main__":
    validate()
```

---

## 4. Phase 4: Live DMS Deployment & Reload

Symlink the plugin directly to the user's DMS plugins directory for live testing:

```bash
# 1. Symlink into DMS user plugins
mkdir -p ~/.config/DankMaterialShell/plugins
ln -sf "$PWD" ~/.config/DankMaterialShell/plugins/<myPluginId>

# 2. Restart DMS shell cleanly
dms restart

# 3. Trigger or query via IPC
dms ipc call <myPluginId> status

# 4. Trigger hot-reload without restarting DMS
dms ipc call plugins reload <myPluginId>
```
