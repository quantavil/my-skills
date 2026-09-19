# My-MCPs Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone sister project `my-mcps` in `/home/quantavil/Documents/my-mcps` to centrally manage, version-lock, auto-document, and deploy Model Context Protocol (MCP) servers across Antigravity, Claude Code, Claude Desktop, Cursor, and OpenCode with non-destructive config merges and secret interpolation.

**Architecture:**
A Bun and TypeScript CLI application mirroring the architecture of `my-skills`. It uses a declarative server manifest (`mcp-servers.json`), a version/integrity lockfile (`mcp-lock.json`), and safe agent adapters that merge servers into host configurations without overwriting user-defined servers. Secrets are handled via `.env` interpolation at deploy time so no credentials are committed to git.

**Tech Stack:** Bun, TypeScript, Node.js (`fs/promises`, `path`, `os`).

**Spec:** Dedicated MCP configuration, testing, documentation, and deployment manager patterned after `my-skills`.

## Global Constraints

- Standalone directory: `/home/quantavil/Documents/my-mcps`.
- Pure Bun & TypeScript without unnecessary external dependencies.
- Zero plaintext secrets in Git (`.env` must be gitignored; `.env.example` committed).
- Non-destructive merges: existing servers and tokens in agent configs must never be overwritten or deleted.
- Managed keys prefixed with `managed-` or identified by a metadata tracking field.
- Full test suite via `bun test`.

---

### Task 1: Project Scaffolding & Git Initialization

**Files:**
- Create: `/home/quantavil/Documents/my-mcps/package.json`
- Create: `/home/quantavil/Documents/my-mcps/tsconfig.json`
- Create: `/home/quantavil/Documents/my-mcps/.gitignore`
- Create: `/home/quantavil/Documents/my-mcps/run.sh`
- Create: `/home/quantavil/Documents/my-mcps/.env.example`
- Create: `/home/quantavil/Documents/my-mcps/README.md`

**Interfaces:**
- Produces: Base project structure runnable via `./run.sh` or `bun run <script>`.

- [ ] **Step 1: Create directory `/home/quantavil/Documents/my-mcps`**

Run: `mkdir -p /home/quantavil/Documents/my-mcps`

- [ ] **Step 2: Create `package.json`**

```json
{
  "name": "my-mcps",
  "type": "module",
  "private": true,
  "bin": {
    "my-mcps": "./run.sh"
  },
  "scripts": {
    "setup": "./run.sh deploy",
    "deploy": "./run.sh deploy",
    "check": "./run.sh check",
    "test": "bun test",
    "sync": "./run.sh sync"
  },
  "devDependencies": {
    "@types/bun": "^1.4.2",
    "bun-types": "^1.4.2"
  }
}
```

- [ ] **Step 3: Create `tsconfig.json`, `.gitignore`, and `run.sh`**

`.gitignore`:
```
node_modules/
.env
*.log
.DS_Store
```

`run.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bun "${DIR}/index.ts" "$@"
```
Run: `chmod +x /home/quantavil/Documents/my-mcps/run.sh`

- [ ] **Step 4: Create `.env.example`**

```bash
# Example secrets for managed MCP servers
GITHUB_PERSONAL_ACCESS_TOKEN=
BRAVE_API_KEY=
```

- [ ] **Step 5: Initialize Git repository**

Run in `/home/quantavil/Documents/my-mcps`:
`git init`

---

### Task 2: Core Manifest & Secret Interpolation Engine

**Files:**
- Create: `/home/quantavil/Documents/my-mcps/mcp-servers.json`
- Create: `/home/quantavil/Documents/my-mcps/src/secrets.ts`
- Test: `/home/quantavil/Documents/my-mcps/tests/secrets.test.ts`

**Interfaces:**
- Consumes: `.env` file and manifest JSON strings.
- Produces: `interpolateSecrets(template: string, env: Record<string, string>): { resolved: string; missing: string[] }`

- [ ] **Step 1: Define initial `mcp-servers.json`**

```json
{
  "$schema": "https://json.schemastore.org/mcp-servers.json",
  "servers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/quantavil/Documents"],
      "description": "Local filesystem access for documents and projects"
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"],
      "description": "Web page and URL content fetcher"
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "description": "Knowledge graph persistent memory server"
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
      },
      "description": "GitHub repos, issues, and PR management"
    }
  }
}
```

- [ ] **Step 2: Write failing test in `tests/secrets.test.ts`**

```typescript
import { expect, test } from "bun:test";
import { interpolateSecrets, parseEnv } from "../src/secrets";

test("parseEnv parses key-value pairs ignoring comments", () => {
  const envText = "FOO=bar\n# comment\nBAZ=qux\n";
  const env = parseEnv(envText);
  expect(env.FOO).toBe("bar");
  expect(env.BAZ).toBe("qux");
  expect(env["# comment"]).toBeUndefined();
});

test("interpolateSecrets replaces placeholders and reports missing keys", () => {
  const template = JSON.stringify({ token: "${MY_SECRET}", fallback: "${NOT_FOUND}" });
  const { resolved, missing } = interpolateSecrets(template, { MY_SECRET: "xyz123" });
  const parsed = JSON.parse(resolved);
  expect(parsed.token).toBe("xyz123");
  expect(missing).toEqual(["NOT_FOUND"]);
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /home/quantavil/Documents/my-mcps && bun test tests/secrets.test.ts`
Expected: FAIL with module not found.

- [ ] **Step 4: Implement `src/secrets.ts`**

```typescript
export function parseEnv(content: string): Record<string, string> {
  const env: Record<string, string> = {};
  for (const rawLine of content.split("\n")) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eqIdx = line.indexOf("=");
    if (eqIdx === -1) continue;
    const key = line.slice(0, eqIdx).trim();
    let val = line.slice(eqIdx + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    env[key] = val;
  }
  return env;
}

export function interpolateSecrets(
  template: string,
  env: Record<string, string>
): { resolved: string; missing: string[] } {
  const missing: string[] = [];
  const resolved = template.replace(/\${([A-Z0-9_]+)}/g, (match, varName) => {
    const val = env[varName];
    if (val === undefined || val === "") {
      missing.push(varName);
      return match;
    }
    return val;
  });
  return { resolved, missing: Array.from(new Set(missing)) };
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/quantavil/Documents/my-mcps && bun test tests/secrets.test.ts`
Expected: PASS.

---

### Task 3: Non-Destructive Multi-Agent Deployer

**Files:**
- Create: `/home/quantavil/Documents/my-mcps/src/deployer.ts`
- Test: `/home/quantavil/Documents/my-mcps/tests/deployer.test.ts`

**Interfaces:**
- Consumes: Manifest object with resolved env vars.
- Produces: `deployToAgents(servers: Record<string, any>, homeDir?: string): Promise<DeployReport[]>`
- Supports:
  - Antigravity CLI: `~/.gemini/antigravity-cli/mcp_config.json` (`mcpServers`)
  - Claude Desktop: `~/.config/Claude/claude_desktop_config.json` (`mcpServers`)
  - Claude Code: `~/.claude.json` (`mcpServers`)
  - Cursor: `~/.cursor/mcp.json` (`mcpServers`)
  - OpenCode: `~/.config/opencode/opencode.json` (`mcp`)

- [ ] **Step 1: Write failing test in `tests/deployer.test.ts`**

```typescript
import { expect, test, beforeEach, afterEach } from "bun:test";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { mergeMcpConfig } from "../src/deployer";

test("mergeMcpConfig merges managed servers without overwriting user servers", () => {
  const existingConfig = {
    mcpServers: {
      "user-custom-server": { command: "custom-cmd", args: [] },
      "managed-old": { command: "old-cmd", args: [] }
    }
  };

  const managedServers = {
    filesystem: { command: "npx", args: ["server-filesystem"] }
  };

  const updated = mergeMcpConfig(existingConfig, managedServers, "mcpServers", "managed-");

  // Preserves user servers
  expect(updated.mcpServers["user-custom-server"]).toBeDefined();
  // Removes obsolete managed servers
  expect(updated.mcpServers["managed-old"]).toBeUndefined();
  // Adds new managed server with prefix
  expect(updated.mcpServers["managed-filesystem"]).toBeDefined();
  expect(updated.mcpServers["managed-filesystem"].command).toBe("npx");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/quantavil/Documents/my-mcps && bun test tests/deployer.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement `src/deployer.ts`**

```typescript
import fs from "node:fs";
import path from "node:path";

export interface AgentTarget {
  name: string;
  configPath: string;
  rootKey: "mcpServers" | "mcp";
  prefix: string;
}

export function mergeMcpConfig(
  existingConfig: any,
  managedServers: Record<string, any>,
  rootKey: "mcpServers" | "mcp" = "mcpServers",
  prefix: string = "managed-"
): any {
  const result = { ...(existingConfig || {}) };
  const currentServers = { ...(result[rootKey] || {}) };

  // Remove previously managed servers
  for (const key of Object.keys(currentServers)) {
    if (key.startsWith(prefix)) {
      delete currentServers[key];
    }
  }

  // Add updated managed servers
  for (const [name, def] of Object.entries(managedServers)) {
    const { description, ...cleanDef } = def;
    currentServers[`${prefix}${name}`] = cleanDef;
  }

  result[rootKey] = currentServers;
  return result;
}

export function getAgentTargets(homeDir: string): AgentTarget[] {
  return [
    {
      name: "Antigravity CLI",
      configPath: path.join(homeDir, ".gemini/antigravity-cli/mcp_config.json"),
      rootKey: "mcpServers",
      prefix: "managed-"
    },
    {
      name: "Claude Desktop",
      configPath: path.join(homeDir, ".config/Claude/claude_desktop_config.json"),
      rootKey: "mcpServers",
      prefix: "managed-"
    },
    {
      name: "Claude Code",
      configPath: path.join(homeDir, ".claude.json"),
      rootKey: "mcpServers",
      prefix: "managed-"
    },
    {
      name: "Cursor",
      configPath: path.join(homeDir, ".cursor/mcp.json"),
      rootKey: "mcpServers",
      prefix: "managed-"
    },
    {
      name: "OpenCode",
      configPath: path.join(homeDir, ".config/opencode/opencode.json"),
      rootKey: "mcp",
      prefix: "managed-"
    }
  ];
}

export async function deployToAgents(
  managedServers: Record<string, any>,
  homeDir: string = process.env.HOME || ""
): Promise<string[]> {
  const targets = getAgentTargets(homeDir);
  const reports: string[] = [];

  for (const target of targets) {
    try {
      const dir = path.dirname(target.configPath);
      await fs.promises.mkdir(dir, { recursive: true });

      let existing = {};
      if (fs.existsSync(target.configPath)) {
        try {
          const raw = await fs.promises.readFile(target.configPath, "utf-8");
          existing = JSON.parse(raw);
        } catch {
          existing = {};
        }
      }

      const merged = mergeMcpConfig(existing, managedServers, target.rootKey, target.prefix);
      await fs.promises.writeFile(target.configPath, JSON.stringify(merged, null, 2) + "\n");
      reports.push(`✓ ${target.name}: deployed ${Object.keys(managedServers).length} servers to ${target.configPath}`);
    } catch (err) {
      reports.push(`✗ ${target.name}: ${(err as Error).message}`);
    }
  }

  return reports;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/quantavil/Documents/my-mcps && bun test tests/deployer.test.ts`
Expected: PASS.

---

### Task 4: Auto-Documentation Generator (`README.md`) & Index CLI

**Files:**
- Create: `/home/quantavil/Documents/my-mcps/src/catalog.ts`
- Create: `/home/quantavil/Documents/my-mcps/index.ts`
- Test: `/home/quantavil/Documents/my-mcps/tests/catalog.test.ts`

**Interfaces:**
- Consumes: Manifest definitions from `mcp-servers.json`.
- Produces: `renderReadmeTable(servers: Record<string, any>): string` to keep `README.md` catalog up to date.

- [ ] **Step 1: Write failing test in `tests/catalog.test.ts`**

```typescript
import { expect, test } from "bun:test";
import { renderReadmeTable } from "../src/catalog";

test("renderReadmeTable produces formatted markdown table", () => {
  const servers = {
    filesystem: {
      command: "npx",
      args: ["-y", "@modelcontextprotocol/server-filesystem"],
      description: "Local filesystem operations"
    }
  };
  const table = renderReadmeTable(servers);
  expect(table).toContain("| `filesystem` | Local filesystem operations | `npx -y @modelcontextprotocol/server-filesystem` |");
});
```

- [ ] **Step 2: Implement `src/catalog.ts`**

```typescript
export const START_TAG = "<!-- mcp:start -->";
export const END_TAG = "<!-- mcp:end -->";

export function renderReadmeTable(servers: Record<string, any>): string {
  const headers = [
    "| Server | Description | Command | Required Secrets |",
    "| --- | --- | --- | --- |"
  ];

  const rows = Object.entries(servers).sort(([a], [b]) => a.localeCompare(b)).map(([name, def]) => {
    const cmd = `\`${def.command} ${(def.args || []).join(" ")}\``;
    const desc = (def.description || "").replace(/\|/g, "\\|");
    const envVars = Object.keys(def.env || {});
    const secrets = envVars.length > 0 ? envVars.map(v => `\`${v}\``).join(", ") : "None";
    return `| \`${name}\` | ${desc} | ${cmd} | ${secrets} |`;
  });

  return [...headers, ...rows].join("\n");
}

export function updateReadmeContent(readme: string, table: string): string {
  const re = new RegExp(`${START_TAG}[\\s\\S]*?${END_TAG}`);
  if (!re.test(readme)) {
    throw new Error(`README.md is missing markers ${START_TAG} and ${END_TAG}`);
  }
  return readme.replace(re, `${START_TAG}\n\n${table}\n\n${END_TAG}`);
}
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd /home/quantavil/Documents/my-mcps && bun test tests/catalog.test.ts`
Expected: PASS.

- [ ] **Step 4: Implement `index.ts` CLI Entrypoint**

Wire up commands:
- `bun index.ts deploy`: Interplate secrets, update README, and deploy to agent targets.
- `bun index.ts check`: Ensure README is up to date and no env keys are unrepresented in `.env.example`.
- `bun index.ts test`: Run test suites.

---

### Task 5: End-to-End Execution & Verification

**Files:**
- Execute verification commands in `/home/quantavil/Documents/my-mcps`.

- [ ] **Step 1: Run complete test suite**

Run: `cd /home/quantavil/Documents/my-mcps && bun test`
Expected: All tests pass.

- [ ] **Step 2: Verify `bun run check`**

Run: `cd /home/quantavil/Documents/my-mcps && bun run check`
Expected: Clean pass with status 0.

- [ ] **Step 3: Commit initial codebase in `my-mcps`**

Run:
`git add -A && git commit -m "feat: initial commit for my-mcps manager"`
