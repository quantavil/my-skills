import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { checkName, readManifest } from './manifest';
import { sourceHash } from './hash';
import { parseFrontmatter, sourceDir } from './skills';
import type { Repo } from './repo';

/** The CLI's vendor-neutral target, used only inside temporary staging. */
export const AGENT = 'universal';

export interface LockEntry {
  source: string;
  sourceType?: string;
  sourceUrl?: string;
  skillPath?: string;
  computedHash?: string;
}
/** Owned by the skills CLI for upstream skills. Used for provenance; integrity lives in skills.json. */
export type Lock = Record<string, LockEntry>;

/** Missing lock is fine. A malformed one is an error, so it is never silently replaced. */
export async function readLock(repo: Repo): Promise<Lock> {
  const file = Bun.file(repo.lockPath);
  if (!(await file.exists())) return {};
  const raw = await file.json();
  if (!raw || raw.version !== 1 || !raw.skills || typeof raw.skills !== 'object' || Array.isArray(raw.skills)) {
    throw new Error('skills-lock.json: expected version 1 and a skills object');
  }
  for (const [name, entry] of Object.entries(raw.skills)) {
    checkName(name);
    const value = entry as Partial<LockEntry> | null;
    if (!value || typeof value.source !== 'string' || !value.source.trim() ||
      ['sourceType', 'sourceUrl', 'skillPath', 'computedHash'].some(key =>
        value[key as keyof LockEntry] !== undefined && typeof value[key as keyof LockEntry] !== 'string')) {
      throw new Error(`skills-lock.json: invalid entry for ${name}`);
    }
  }
  return raw.skills as Lock;
}

export async function writeLock(repo: Repo, lock: Lock): Promise<void> {
  const sorted: Lock = {};
  for (const k of Object.keys(lock).sort()) {
    const entry = lock[k];
    if (entry !== undefined) sorted[k] = entry;
  }
  await Bun.write(repo.lockPath, JSON.stringify({ version: 1, skills: sorted }, null, 2) + '\n');
}

/** Bare `add <repo>` means every skill in it. The `*` is injected here rather than
 *  typed, so the shell never gets a chance to glob it — spawn takes an argv array. */
export function addArgs(args: string[]): string[] {
  const picked = args.some((a) => a === '-s' || a === '--skill');
  return ['add', ...args, ...(picked ? [] : ['-s', '*']), '-a', AGENT, '--copy', '-y'];
}

/** `skills remove` only knows skill names, so "drop everything from obra/superpowers"
 *  has to be expanded against the lock here. Accepts either form. */
export function resolveNames(args: string[], lock: Lock): string[] {
  const out = new Set<string>();
  const unmatched: string[] = [];

  for (const arg of args) {
    if (lock[arg]) {
      out.add(arg);
      continue;
    }
    const fromRepo = Object.keys(lock).filter((n) => lock[n]?.source === arg || lock[n]?.sourceUrl === arg);
    if (!fromRepo.length) unmatched.push(arg);
    for (const n of fromRepo) out.add(n);
  }

  if (unmatched.length) throw new Error(`not in this collection: ${unmatched.join(', ')}`);
  return [...out];
}

/** Run upstream tooling in an isolated checkout; never use the project's .agents directory as scratch. */
export async function runSkills(repo: Repo, args: string[], force = false): Promise<string[]> {
  const cli = path.join(repo.root, 'node_modules/skills/bin/cli.mjs');
  if (!fs.existsSync(cli)) throw new Error('the pinned skills CLI is missing: run bun install');
  const stage = fs.mkdtempSync(path.join(os.tmpdir(), 'my-skills-vendor-'));
  try {
    const stagedRepo = { ...repo, lockPath: path.join(stage, 'skills-lock.json') };
    const lock = await readLock(repo);
    await writeLock(stagedRepo, lock);
    await Bun.$`${process.execPath} ${cli} ${args}`.cwd(stage);
    const staged = path.join(stage, '.agents/skills');
    const incoming = await readLock(stagedRepo);
    const manifest = await readManifest(repo);
    if (!fs.existsSync(staged)) throw new Error('upstream command produced no skill folders');
    const names = fs.readdirSync(staged);
    const requested = args.filter((_, i) => args[i - 1] === '-s' || args[i - 1] === '--skill');
    for (const name of requested) {
      if (name !== '*' && !names.includes(name)) throw new Error(`upstream did not install requested skill: ${name}`);
    }
    // Validate everything before replacing any existing folder.
    for (const name of names) {
      checkName(name);
      if (manifest?.superskills[name]) throw new Error(`${name}: a bundle already uses this name; rename or remove the bundle first`);
      const meta = manifest?.skills[name];
      const existing = sourceDir(repo, name);
      if (!force && fs.existsSync(existing)) {
        if (!meta || meta.type === 'local') throw new Error(`${name}: refusing to replace a local skill; pass --force to replace it`);
        if (sourceHash(existing) !== meta.contentHash) throw new Error(`${name}: refusing to replace local edits; accept them or pass --force`);
        if (lock[name]?.source !== incoming[name]?.source) throw new Error(`${name}: source collision; pass --force to replace it`);
      }
      if (!incoming[name] || !fs.existsSync(path.join(staged, name, 'SKILL.md'))) {
        throw new Error(`incomplete upstream skill: ${name}`);
      }
      const fields = parseFrontmatter(fs.readFileSync(path.join(staged, name, 'SKILL.md'), 'utf8'));
      if (fields.name && fields.name !== name) throw new Error(`${name}: upstream folder name does not match its skill name`);
    }
    fs.mkdirSync(repo.skillsDir, { recursive: true });
    const installed: Array<{ name: string; dest: string }> = [];
    const backups = path.join(stage, 'backups');
    fs.mkdirSync(backups);
    try {
      for (const name of names) {
        const dest = sourceDir(repo, name);
        if (fs.existsSync(dest)) fs.cpSync(dest, path.join(backups, name), { recursive: true });
        installed.push({ name, dest });
        fs.rmSync(dest, { recursive: true, force: true });
        fs.cpSync(path.join(staged, name), dest, { recursive: true });
        if (dest.startsWith(repo.sourcesDir + path.sep)) fs.renameSync(path.join(dest, 'SKILL.md'), path.join(dest, 'GUIDE.md'));
        lock[name] = incoming[name]!;
      }
      await writeLock(repo, lock);
    } catch (err) {
      for (const { name, dest } of installed) {
        fs.rmSync(dest, { recursive: true, force: true });
        if (fs.existsSync(path.join(backups, name))) fs.cpSync(path.join(backups, name), dest, { recursive: true });
      }
      throw err;
    }
    return names;
  } catch (err) {
    throw new Error(`skills ${args.join(' ')} failed: ${(err as Error).message}`);
  } finally {
    fs.rmSync(stage, { recursive: true, force: true });
  }
}
