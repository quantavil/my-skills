# Enable and Disable MCP Servers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a first-class feature to enable and disable MCP servers via `./run.sh enable <name>` and `./run.sh disable <name>`, persisting state in `mcp-servers.json` so inactive servers remain configured in the repository but are pruned from deployed AI coding agent configs.

**Architecture:** Extend manifest schema with optional `enabled: boolean` property (defaulting to `true`). In `index.ts`, filter for active servers during deployment (`runDeploy`), display `[enabled]` / `[disabled]` status in `runList`, and add `toggleServer()` to update `mcp-servers.json` and immediately trigger non-destructive redeployment.

**Tech Stack:** TypeScript, Bun runtime (`bun:test`, `Bun.spawn`, `Bun.TOML`), JSON schemas.

**Spec:** Local requirements specified by user: keep servers in repository manifest while inactive, support enable/disable toggling, and verify non-destructive propagation across all 6 agent targets (`Antigravity CLI`, `Codex CLI`, `Claude Desktop`, `Claude Code`, `Cursor`, `OpenCode`).

## Global Constraints

- Never commit `.env` or plaintext API keys; only `.env.example` with template keys.
- Preserve non-managed user servers across all agent target configs.
- Strict use of `bun` and `bunx` (no `npx`).
- Pure TypeScript implementation with zero extra npm dependencies.
- All commands runnable via `./run.sh <command>`.

---

### Task 1: Core Toggle Logic & Deploy Filtering

**Files:**
- Modify: `/home/quantavil/Documents/my-mcps/index.ts`
- Test: `/home/quantavil/Documents/my-mcps/tests/toggle.test.ts`

**Interfaces:**
- Produces:
  - `export async function setServerEnabled(rootDir: string, serverName: string, enabled: boolean): Promise<{ success: boolean; error?: string }>`
  - Updated `runDeploy(rootDir?: string, homeDir?: string)`: filters out any server with `enabled === false` before secret interpolation and deployment.
  - Updated `runList(rootDir?: string)`: outputs `• <name> [enabled]` or `• <name> [disabled]`.

- [ ] **Step 1: Write failing tests in `tests/toggle.test.ts`**

```typescript
import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { setServerEnabled, runDeploy, runList } from "../index";

describe("setServerEnabled and deploy filtering", () => {
  let tempDir: string;
  let tempHome: string;

  beforeEach(async () => {
    tempDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), "mcp-toggle-test-"));
    tempHome = await fs.promises.mkdtemp(path.join(os.tmpdir(), "mcp-home-toggle-"));

    const initialManifest = {
      servers: {
        serverA: {
          command: "bunx",
          args: ["server-a"],
          description: "Server A description"
        },
        serverB: {
          command: "bunx",
          args: ["server-b"],
          description: "Server B description"
        }
      }
    };
    await fs.promises.writeFile(
      path.join(tempDir, "mcp-servers.json"),
      JSON.stringify(initialManifest, null, 2)
    );
  });

  afterEach(async () => {
    await fs.promises.rm(tempDir, { recursive: true, force: true });
    await fs.promises.rm(tempHome, { recursive: true, force: true });
  });

  test("setServerEnabled sets enabled: false when disabling existing server", async () => {
    const res = await setServerEnabled(tempDir, "serverA", false);
    expect(res.success).toBe(true);

    const updated = JSON.parse(await fs.promises.readFile(path.join(tempDir, "mcp-servers.json"), "utf-8"));
    expect(updated.servers.serverA.enabled).toBe(false);
  });

  test("setServerEnabled returns error when server does not exist", async () => {
    const res = await setServerEnabled(tempDir, "nonexistent", false);
    expect(res.success).toBe(false);
    expect(res.error).toContain("not found");
  });

  test("runDeploy excludes disabled servers from deployed configs", async () => {
    await setServerEnabled(tempDir, "serverA", false);
    const ok = await runDeploy(tempDir, tempHome);
    expect(ok).toBe(true);

    const claudePath = path.join(tempHome, ".claude.json");
    const claude = JSON.parse(await fs.promises.readFile(claudePath, "utf-8"));
    expect(claude.mcpServers["managed-serverA"]).toBeUndefined();
    expect(claude.mcpServers["managed-serverB"]).toBeDefined();
  });

  test("enabling a disabled server re-adds it to deployed configs", async () => {
    await setServerEnabled(tempDir, "serverA", false);
    await runDeploy(tempDir, tempHome);

    await setServerEnabled(tempDir, "serverA", true);
    await runDeploy(tempDir, tempHome);

    const claudePath = path.join(tempHome, ".claude.json");
    const claude = JSON.parse(await fs.promises.readFile(claudePath, "utf-8"));
    expect(claude.mcpServers["managed-serverA"]).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bun test tests/toggle.test.ts` in `/home/quantavil/Documents/my-mcps`
Expected: FAIL (`setServerEnabled is not a function` or import error).

- [ ] **Step 3: Implement `setServerEnabled` and update `runDeploy` & `runList` in `index.ts`**

In `index.ts`:
1. Implement `setServerEnabled`:
```typescript
export async function setServerEnabled(
  rootDir: string,
  serverName: string,
  enabled: boolean
): Promise<{ success: boolean; error?: string }> {
  const manifestPath = path.join(rootDir, "mcp-servers.json");
  if (!fs.existsSync(manifestPath)) {
    return { success: false, error: `Manifest file not found at ${manifestPath}` };
  }
  const manifestRaw = await fs.promises.readFile(manifestPath, "utf-8");
  const manifest = JSON.parse(manifestRaw);
  if (!manifest.servers || !manifest.servers[serverName]) {
    return { success: false, error: `Server '${serverName}' not found in manifest` };
  }

  if (enabled) {
    delete manifest.servers[serverName].enabled; // default is enabled
  } else {
    manifest.servers[serverName].enabled = false;
  }

  await fs.promises.writeFile(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
  return { success: true };
}
```

2. In `runDeploy`: filter servers:
```typescript
  const allServers = manifest.servers || {};
  const activeServers: Record<string, any> = {};
  for (const [name, def] of Object.entries(allServers)) {
    if ((def as any).enabled !== false) {
      activeServers[name] = def;
    }
  }
```
Pass `activeServers` to `interpolateSecrets` and `deployToAgents`.

3. In `runList`:
Format status:
```typescript
  for (const [name, def] of Object.entries(servers)) {
    const d = def as any;
    const isEnabled = d.enabled !== false;
    const statusTag = isEnabled ? "\x1b[32m[enabled]\x1b[0m" : "\x1b[31m[disabled]\x1b[0m";
    const cmd = `${d.command} ${(d.args || []).join(" ")}`;
    const envKeys = d.env ? Object.keys(d.env) : [];
    console.log(`• \x1b[1m${name}\x1b[0m ${statusTag}: ${d.description || ""}`);
    console.log(`  Command: ${cmd}`);
    if (envKeys.length > 0) {
      console.log(`  Secrets: ${envKeys.join(", ")}`);
    }
    console.log();
  }
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `bun test tests/toggle.test.ts`
Expected: PASS (4 passing).

- [ ] **Step 5: Commit**

```bash
git add tests/toggle.test.ts index.ts
git commit -m "feat: add setServerEnabled and filter disabled servers during deploy"
```

---

### Task 2: CLI Commands (`enable`, `disable`) & Help Integration

**Files:**
- Modify: `/home/quantavil/Documents/my-mcps/index.ts`
- Modify: `/home/quantavil/Documents/my-mcps/tests/cli.test.ts`

**Interfaces:**
- Produces:
  - CLI command `enable <name>`: calls `setServerEnabled(rootDir, name, true)` then triggers `runDeploy()`.
  - CLI command `disable <name>`: calls `setServerEnabled(rootDir, name, false)` then triggers `runDeploy()`.
  - Updated `printHelp()` documenting `enable` and `disable`.

- [ ] **Step 1: Add test in `tests/cli.test.ts` for enable and disable commands**

Add tests verifying:
- Calling `runEnable(serverName)` enables the server and updates agent configs.
- Calling `runDisable(serverName)` disables the server and removes it from agent configs.

- [ ] **Step 2: Implement CLI commands `runEnable` and `runDisable` in `index.ts`**

```typescript
export async function runEnable(
  serverName?: string,
  rootDir: string = import.meta.dir,
  homeDir: string = process.env.HOME || ""
): Promise<boolean> {
  if (!serverName) {
    console.error("✗ Usage: ./run.sh enable <server-name>");
    return false;
  }
  const res = await setServerEnabled(rootDir, serverName, true);
  if (!res.success) {
    console.error(`✗ ${res.error}`);
    return false;
  }
  console.log(`✓ Server '${serverName}' enabled`);
  return await runDeploy(rootDir, homeDir);
}

export async function runDisable(
  serverName?: string,
  rootDir: string = import.meta.dir,
  homeDir: string = process.env.HOME || ""
): Promise<boolean> {
  if (!serverName) {
    console.error("✗ Usage: ./run.sh disable <server-name>");
    return false;
  }
  const res = await setServerEnabled(rootDir, serverName, false);
  if (!res.success) {
    console.error(`✗ ${res.error}`);
    return false;
  }
  console.log(`✓ Server '${serverName}' disabled (inactive in repo, removed from agent targets)`);
  return await runDeploy(rootDir, homeDir);
}
```

Update `main(args)` to handle `"enable"` and `"disable"`, and update `printHelp()`.

- [ ] **Step 3: Run full test suite**

Run: `bun test` in `/home/quantavil/Documents/my-mcps`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add index.ts tests/cli.test.ts
git commit -m "feat: add enable and disable CLI commands with automatic redeploy"
```

---

### Task 3: Live Verification & Re-verification of All MCPs

**Files:**
- Execute against `/home/quantavil/Documents/my-mcps`

- [ ] **Step 1: Test disabling an MCP server (e.g. `blender`)**
Run: `./run.sh disable blender`
Verify:
- `mcp-servers.json` has `"blender": { ... "enabled": false }`
- Agent target configs (`~/.gemini/antigravity-cli/mcp_config.json`, `~/.codex/config.toml`, `~/.claude.json`, etc.) have 9 servers (`managed-blender` removed).
- `./run.sh list` shows `• blender [disabled]`.

- [ ] **Step 2: Test re-enabling the MCP server**
Run: `./run.sh enable blender`
Verify:
- `mcp-servers.json` has `blender` active.
- Agent target configs have 10 servers (`managed-blender` restored).
- `./run.sh list` shows `• blender [enabled]`.

- [ ] **Step 3: Run test suite & check**
Run: `bun test && ./run.sh check`

- [ ] **Step 4: Commit & push to GitHub**
Commit and push clean updates to GitHub repository `quantavil/my-mcps`.
