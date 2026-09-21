#!/usr/bin/env bun
// Manages the vendored skill collection and keeps README.md's table in sync.
//   bun run add <repo> [-s <skill>...]   vendor a repo's skills, all of them by default
//   bun run remove <skill|repo>...       drop skills, by name or by upstream repo
//   bun run sync                         refetch everything at latest upstream
//   bun run deploy                       deploy skills globally to all AI agents
//   bun run check                        exit 1 if README.md is stale or unpinned skills exist (CI)
//   bun run test                         asserts
//   bun index.ts                         rebuild the table & auto-deploy

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// `openclaw` is the one agent whose project dir is a plain `skills/` rather than a
// dotfolder, so it is used purely as a path selector — nothing OpenClaw-specific.
const AGENT = 'openclaw';
const ROOT_DIR = import.meta.dirname;
const SKILLS_DIR = path.join(ROOT_DIR, 'skills');
const LOCK = path.join(ROOT_DIR, 'skills-lock.json');
const README = path.join(ROOT_DIR, 'README.md');
const START = '<!-- skills:start -->';
const END = '<!-- skills:end -->';
const UNSOURCED = 'Unsourced';
const HOME = os.homedir();

interface LockEntry {
  source: string;
  sourceType?: string;
  sourceUrl?: string;
  skillPath?: string;
  computedHash?: string;
}
type Lock = Record<string, LockEntry>;
interface Skill {
  name: string;
  dir: string;
  description: string;
}

interface SymlinkTarget {
  name: string;
  dir: string;
}

const GLOBAL_SYMLINK_TARGETS: SymlinkTarget[] = [
  { name: 'Antigravity CLI (Direct)', dir: path.join(HOME, '.gemini/antigravity-cli/skills') },
  { name: 'Antigravity (~/.antigravity)', dir: path.join(HOME, '.antigravity/skills') },
  { name: 'Antigravity (~/.gemini/skills)', dir: path.join(HOME, '.gemini/skills') },
  { name: 'Codex CLI', dir: path.join(HOME, '.codex/skills') },
  { name: 'Claude Code', dir: path.join(HOME, '.claude/skills') },
  { name: 'OpenCode', dir: path.join(HOME, '.config/opencode/skills') },
  { name: 'Cursor', dir: path.join(HOME, '.cursor/skills') },
  { name: 'Universal Agents (~/.agents)', dir: path.join(HOME, '.agents/skills') },
  { name: 'Universal Agents (~/.config/agents)', dir: path.join(HOME, '.config/agents/skills') },
];

/** Fast native SHA-256 computation using Bun's built-in CryptoHasher. */
export function computeHash(content: string): string {
  return new Bun.CryptoHasher('sha256').update(content).digest('hex');
}

/** Pull the YAML frontmatter block out of a SKILL.md and validate critical agent fields. */
export function parseFrontmatter(text: string): { name?: string; description?: string } {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m?.[1]) throw new Error('no YAML frontmatter');
  const parsed = (Bun.YAML.parse(m[1]) ?? {}) as { name?: string; description?: string };

  if (parsed.name !== undefined) {
    if (typeof parsed.name !== 'string' || !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(parsed.name)) {
      throw new Error(`invalid name "${parsed.name}": must be lowercase alphanumeric with hyphens`);
    }
  }

  if (typeof parsed.description !== 'string' || !parsed.description.trim()) {
    throw new Error('description cannot be empty');
  }

  if (parsed.description.length > 1024) {
    throw new Error(`description is too long (${parsed.description.length} chars, max 1024)`);
  }

  return parsed;
}

/** Collapse whitespace and escape pipes so a description can't break the table. */
export function cell(s: string): string {
  return s.replace(/\s+/g, ' ').replace(/\|/g, '\\|').trim();
}

export function sourceLink(e?: LockEntry): string {
  if (!e) return UNSOURCED;
  const url = e.sourceUrl ?? (/^[\w.-]+\/[\w.-]+$/.test(e.source) ? `https://github.com/${e.source}` : null);
  return url ? `[${e.source}](${url})` : e.source;
}

/** Swap the block between the markers. Replacement is a function so `$&` in a description is literal. */
export function render(readme: string, table: string): string {
  const re = new RegExp(`${START}[\\s\\S]*?${END}`);
  if (!re.test(readme)) throw new Error(`README.md is missing the ${START} / ${END} markers`);
  return readme.replace(re, () => `${START}\n\n${table}\n\n${END}`);
}

/** One section per upstream repo. Agents flatten skills by name on install, so a
 *  duplicate name is a real conflict no matter how the folders are arranged. */
export function buildMarkdown(skills: Skill[], lock: Lock): string {
  const seen = new Map<string, string>();
  for (const s of skills) {
    const prev = seen.get(s.name);
    if (prev) throw new Error(`two skills both named "${s.name}": skills/${prev}/ and skills/${s.dir}/`);
    seen.set(s.name, s.dir);
  }

  // Keyed on the bare source, not its rendered link, so one repo can't split into
  // two sections just because some entries carry a sourceUrl and others don't.
  const groups = new Map<string, { link: string; skills: Skill[] }>();
  for (const s of skills) {
    const entry = lock[s.name];
    const key = entry?.source ?? UNSOURCED;
    const group = groups.get(key) ?? { link: sourceLink(entry), skills: [] };
    group.skills.push(s);
    groups.set(key, group);
  }

  // Unsourced last, everything else alphabetical.
  const keys = [...groups.keys()].sort((a, b) =>
    a === UNSOURCED ? 1 : b === UNSOURCED ? -1 : a.localeCompare(b),
  );

  return keys
    .map((key) => {
      const { link, skills } = groups.get(key)!;
      const rows = skills
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((s) => `| [\`${s.name}\`](skills/${s.dir}/) | ${cell(s.description)} |`);
      return [`### ${link}`, '', '| Skill | Use it when |', '| --- | --- |', ...rows].join('\n');
    })
    .join('\n\n');
}

/** Bare `add <repo>` means every skill in it. The `*` is injected here rather than
 *  typed, so the shell never gets a chance to glob it — spawn takes an argv array. */
export function addArgs(rest: string[]): string[] {
  const picked = rest.some((a) => a === '-s' || a === '--skill');
  return ['add', ...rest, ...(picked ? [] : ['-s', '*']), '-a', AGENT, '--copy', '-y'];
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

/** Missing lock is fine — a malformed one is not, so only absence is defaulted. */
export const readLock = async (): Promise<Lock> => {
  const file = Bun.file(LOCK);
  if (!(await file.exists())) return {};
  try {
    return ((await file.json()) as { skills?: Lock }).skills ?? {};
  } catch {
    return {};
  }
};

async function run(args: string[]) {
  try {
    await Bun.$`bunx skills ${args}`;
  } catch {
    throw new Error(`skills ${args.join(' ')} failed`);
  }
}

export async function readSkills(): Promise<Skill[]> {
  const glob = new Bun.Glob('*/SKILL.md');
  const files = await Array.fromAsync(glob.scan({ cwd: SKILLS_DIR }));
  return Promise.all(
    files.map(async (rel) => {
      const dir = rel.split('/')[0] ?? rel;
      try {
        const text = await Bun.file(path.join(SKILLS_DIR, rel)).text();
        const { name, description } = parseFrontmatter(text);
        return { name: name ?? dir, dir, description: description ?? '' };
      } catch (e) {
        throw new Error(`skills/${rel}: ${(e as Error).message}`);
      }
    }),
  );
}

export function isUpstreamManaged(entry: LockEntry): boolean {
  return entry.sourceType !== 'local';
}

async function sync() {
  const lock = await readLock();
  const names = Object.keys(lock).filter((name) => { const entry = lock[name]; return entry !== undefined && isUpstreamManaged(entry); });
  if (!names.length) return console.log('no upstream-managed skills to sync');

  // One `add` per repo, not per skill — a repo contributing 14 skills would
  // otherwise be fetched 14 times.
  const byRepo = new Map<string, string[]>();
  for (const n of names) {
    const entry = lock[n];
    if (!entry) continue; // names are lock keys; guard only satisfies noUncheckedIndexedAccess
    const src = entry.sourceUrl ?? entry.source;
    byRepo.get(src)?.push(n) ?? byRepo.set(src, [n]);
  }

  for (const [src, group] of byRepo) {
    console.log(`\n↻ ${src}  (${group.length} skill${group.length > 1 ? 's' : ''})`);
    await run(addArgs([src, ...group.flatMap((n) => ['-s', n])]));
  }
}

export async function reindex(check = false) {
  const before = await Bun.file(README).text();
  const skills = await readSkills();
  const lock = await readLock();

  // Detect and auto-pin unpinned local skills
  let lockModified = false;
  for (const s of skills) {
    if (!lock[s.name]) {
      if (check) {
        console.error(`✗ Unpinned skill: "skills/${s.dir}" is missing from skills-lock.json — run: bun index.ts`);
        process.exit(1);
      }
      const skillText = await Bun.file(path.join(SKILLS_DIR, s.dir, 'SKILL.md')).text();
      const hash = computeHash(skillText);
      lock[s.name] = {
        source: 'quantavil/my-skills',
        sourceType: 'local',
        skillPath: `skills/${s.dir}/SKILL.md`,
        computedHash: hash,
      };
      lockModified = true;
      console.log(`  ✓ Auto-pinned local skill: "${s.name}" -> quantavil/my-skills`);
    }
  }

  if (lockModified && !check) {
    const sortedSkills: Lock = {};
    for (const k of Object.keys(lock).sort()) {
      const entry = lock[k];
      if (entry !== undefined) sortedSkills[k] = entry;
    }
    await Bun.write(LOCK, JSON.stringify({ version: 1, skills: sortedSkills }, null, 2) + '\n');
    console.log(`  ✓ Updated ${LOCK} with newly pinned local skills`);
  }

  const after = render(before, buildMarkdown(skills, lock));

  if (!check) {
    await Bun.write(README, after);
    return console.log(`README.md: ${skills.length} skills indexed`);
  }
  if (after !== before) {
    console.error('README.md is stale — run: bun index.ts');
    process.exit(1);
  }
  console.log(`README.md up to date (${skills.length} skills)`);
}

/** Ensure Antigravity discovers the skills directory globally via ~/.gemini/config/skills.json */
export async function updateGeminiConfig(skillsDir: string = SKILLS_DIR): Promise<void> {
  const configDir = path.join(HOME, '.gemini/config');
  const configFile = path.join(configDir, 'skills.json');
  await fs.promises.mkdir(configDir, { recursive: true });

  let config: { entries?: Array<{ path: string }> } = {};
  const file = Bun.file(configFile);
  if (await file.exists()) {
    try {
      config = await file.json();
    } catch {
      config = {};
    }
  }
  if (!Array.isArray(config.entries)) {
    config.entries = [];
  }

  const normalizedPath = skillsDir.replace(HOME, '~');
  const hasEntry = config.entries.some(
    (e) => e.path === skillsDir || e.path === normalizedPath || path.resolve(e.path.replace(/^~/, HOME)) === path.resolve(skillsDir)
  );

  if (!hasEntry) {
    config.entries.push({ path: skillsDir });
    await Bun.write(configFile, JSON.stringify(config, null, 2) + '\n');
    console.log(`  ✓ Registered in Antigravity config: ${configFile}`);
  } else {
    console.log(`  ✓ Antigravity config up to date: ${configFile}`);
  }
}

/** Ensure OpenCode discovers the skills directory globally via ~/.config/opencode/opencode.json */
export async function updateOpenCodeConfig(skillsDir: string = SKILLS_DIR): Promise<void> {
  const configDir = path.join(HOME, '.config/opencode');
  const configFile = path.join(configDir, 'opencode.json');
  await fs.promises.mkdir(configDir, { recursive: true });

  let config: { $schema?: string; skills?: string[] } = {};
  const file = Bun.file(configFile);
  if (await file.exists()) {
    try {
      config = await file.json();
    } catch {
      config = {};
    }
  }
  if (!config.$schema) {
    config.$schema = 'https://opencode.ai/config.json';
  }
  if (!Array.isArray(config.skills)) {
    config.skills = [];
  }

  const normalizedPath = skillsDir.replace(HOME, '~');
  const hasEntry = config.skills.some(
    (p) => p === skillsDir || p === normalizedPath || path.resolve(p.replace(/^~/, HOME)) === path.resolve(skillsDir)
  );

  if (!hasEntry) {
    config.skills.push(skillsDir);
    await Bun.write(configFile, JSON.stringify(config, null, 2) + '\n');
    console.log(`  ✓ Registered in OpenCode config: ${configFile}`);
  } else {
    console.log(`  ✓ OpenCode config up to date: ${configFile}`);
  }
}

/** Deploy skills globally to all major AI agents (Antigravity, Codex, Claude Code, OpenCode, Universal). */
export async function deployGlobal(skillsDir: string = SKILLS_DIR): Promise<void> {
  console.log('\n🚀 Deploying skills globally to all AI agent targets...');

  // 1. Native config discovery (concurrent)
  await Promise.all([
    updateGeminiConfig(skillsDir),
    updateOpenCodeConfig(skillsDir),
  ]);

  // 2. Discover local skills to link
  const skillEntries = await fs.promises.readdir(skillsDir, { withFileTypes: true });
  const skillDirs = skillEntries
    .filter((d) => d.isDirectory() && fs.existsSync(path.join(skillsDir, d.name, 'SKILL.md')))
    .map((d) => d.name);

  // 3. Concurrent symlink fanout to all agent directories
  await Promise.all(
    GLOBAL_SYMLINK_TARGETS.map(async (target) => {
      try {
        await fs.promises.mkdir(target.dir, { recursive: true });
        let linked = 0;

        for (const skillName of skillDirs) {
          const src = path.join(skillsDir, skillName);
          const dest = path.join(target.dir, skillName);

          try {
            const stat = await fs.promises.lstat(dest).catch(() => null);
            if (stat) {
              if (stat.isSymbolicLink()) {
                const currentTarget = await fs.promises.readlink(dest);
                if (path.resolve(target.dir, currentTarget) === path.resolve(src)) {
                  continue;
                }
                await fs.promises.unlink(dest);
              } else {
                // Real file or directory (e.g. .system in .codex), do not overwrite
                continue;
              }
            }
            await fs.promises.symlink(src, dest);
            linked++;
          } catch (err) {
            console.warn(`    ⚠ Failed to link ${skillName} in ${target.name}: ${(err as Error).message}`);
          }
        }

        // Cleanup stale symlinks in target pointing to skillsDir
        const existingEntries = await fs.promises.readdir(target.dir);
        let cleaned = 0;
        for (const entry of existingEntries) {
          const dest = path.join(target.dir, entry);
          try {
            const stat = await fs.promises.lstat(dest).catch(() => null);
            if (stat && stat.isSymbolicLink()) {
              const targetResolved = path.resolve(target.dir, await fs.promises.readlink(dest));
              if (targetResolved.startsWith(path.resolve(skillsDir)) && !fs.existsSync(targetResolved)) {
                await fs.promises.unlink(dest);
                cleaned++;
              }
            }
          } catch {}
        }

        console.log(`  ✓ ${target.name} (${target.dir}): ${skillDirs.length} skills active${linked ? ` (${linked} newly linked)` : ''}${cleaned ? ` (${cleaned} stale removed)` : ''}`);
      } catch (err) {
        console.warn(`  ✗ Failed deploying to ${target.name}: ${(err as Error).message}`);
      }
    })
  );

  console.log('✓ Global multi-agent deployment complete.\n');
}

function selftest() {
  const ok = (cond: unknown, msg: string) => {
    if (!cond) throw new Error(`selftest: ${msg}`);
  };
  const throws = (fn: () => unknown, msg: string) => {
    try { fn(); } catch { return; }
    throw new Error(`selftest: ${msg}`);
  };

  const fm = parseFrontmatter('---\nname: demo\ndescription: does a | thing\n  over two lines\n---\nbody');
  ok(fm.name === 'demo', 'name');
  ok(cell(fm.description!) === 'does a \\| thing over two lines', 'cell folds lines and escapes pipes');
  ok(sourceLink({ source: 'a/b' }) === '[a/b](https://github.com/a/b)', 'sourceLink links owner/repo');
  ok(sourceLink(undefined) === UNSOURCED, 'sourceLink handles a missing lock entry');

  // Frontmatter lint validations
  throws(() => parseFrontmatter('---\nname: Invalid_Name\ndescription: test\n---'), 'reject bad name charset');
  throws(() => parseFrontmatter('---\nname: test\ndescription: ""\n---'), 'reject empty description');
  throws(() => parseFrontmatter('---\nname: test\ndescription: "   "\n---'), 'reject whitespace description');
  throws(() => parseFrontmatter(`---\nname: test\ndescription: ${'a'.repeat(1025)}\n---`), 'reject oversized description');

  // Hash verification
  ok(computeHash('test') === '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08', 'Bun.CryptoHasher sha256 matches');

  const out = render(`intro\n${START}\nstale\n${END}\noutro`, 'TABLE $& text');
  ok(out === `intro\n${START}\n\nTABLE $& text\n\n${END}\noutro`, 'render swaps the block, $& stays literal');
  ok(render(out, 'again').split('TABLE').length === 1, 'render is idempotent');
  throws(() => render('no markers here', 'x'), 'render must reject a README with no markers');

  ok(addArgs(['o/r']).join(' ').includes('o/r -s *'), 'addArgs defaults a bare repo to every skill');
  ok(!addArgs(['o/r', '-s', 'one']).join(' ').includes('*'), 'addArgs leaves an explicit -s alone');
  ok(!addArgs(['o/r', '--skill', 'one']).join(' ').includes('*'), 'addArgs honours --skill too');

  const lock: Lock = { a: { source: 'o/r' }, b: { source: 'o/r' }, c: { source: 'x/y' } };
  ok(resolveNames(['a'], lock).join() === 'a', 'resolveNames passes a skill name through');
  ok(resolveNames(['o/r'], lock).join() === 'a,b', 'resolveNames expands a repo to its skills');
  ok(resolveNames(['a', 'o/r'], lock).join() === 'a,b', 'resolveNames dedupes overlap');
  throws(() => resolveNames(['nope'], lock), 'resolveNames must reject an unknown target');

  const md = buildMarkdown(
    [
      { name: 'c', dir: 'c', description: 'third' },
      { name: 'b', dir: 'b', description: 'second' },
      { name: 'a', dir: 'a', description: 'first' },
      { name: 'z', dir: 'z', description: 'orphan' },
    ],
    lock,
  );
  ok(md.indexOf('### [o/r]') < md.indexOf('### [x/y]'), 'groups sort alphabetically');
  ok(md.indexOf(`### ${UNSOURCED}`) > md.indexOf('### [x/y]'), 'unsourced group goes last');
  ok(md.indexOf('[`a`]') < md.indexOf('[`b`]'), 'skills sort within a group');
  throws(
    () => buildMarkdown([{ name: 'dup', dir: 'x', description: '' }, { name: 'dup', dir: 'y', description: '' }], {}),
    'buildMarkdown must reject two skills with the same name',
  );

  ok(!isUpstreamManaged({ source: './skills/ditto', sourceType: 'local' }), 'sync preserves locally maintained skills');
  ok(isUpstreamManaged({ source: 'o/r', sourceType: 'github' }), 'sync includes upstream skills');
  ok(isUpstreamManaged({ source: 'o/r' }), 'sync preserves legacy lock behavior');

  console.log('selftest ok');
}

async function main() {
  const [cmd, ...rest] = Bun.argv.slice(2);

  switch (cmd) {
    case 'add': {
      if (!rest.length) throw new Error('usage: bun run add <repo> [-s <skill>...]');
      const before = await readLock();
      await run(addArgs(rest));
      const after = await readLock();
      for (const [name, e] of Object.entries(after)) {
        if (before[name] && before[name].source !== e.source) {
          console.warn(`⚠ "${name}" was replaced: ${before[name].source} → ${e.source}`);
        }
      }
      await reindex();
      await deployGlobal();
      break;
    }

    case 'remove': {
      if (!rest.length) throw new Error('usage: bun run remove <skill|repo>...');
      const names = resolveNames(rest, await readLock());
      console.log(`removing ${names.length}: ${names.join(', ')}`);
      await run(['remove', ...names, '-a', AGENT, '-y']);
      await reindex();
      await deployGlobal();
      break;
    }

    case 'sync':
      await sync();
      await reindex();
      await deployGlobal();
      break;

    case 'deploy':
      await deployGlobal();
      break;

    case 'check':
      await reindex(true);
      break;

    case 'test':
      selftest();
      break;

    default:
      await reindex();
      await deployGlobal();
      break;
  }
}

// A usage mistake should read as one line, not a Bun stack trace into index.ts.
try {
  await main();
} catch (e) {
  console.error(`✗ ${(e as Error).message}`);
  process.exit(1);
}
