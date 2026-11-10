import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { bundleDir, FINDER, GITHUB_SLUG, type Bundle, type Config, type Repo } from './config';

export interface Skill {
  name: string;
  dir: string;
  description: string;
}

const SKIP = new Set(['.git', 'node_modules', '__pycache__', '.venv']);

export function parseSkill(dir: string): Skill {
  const file = path.join(dir, 'SKILL.md');
  const m = fs.readFileSync(file, 'utf8').match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m?.[1]) throw new Error(`${file}: no YAML frontmatter`);
  let fm: { name?: unknown; description?: unknown };
  try {
    fm = (Bun.YAML.parse(m[1]) ?? {}) as typeof fm;
  } catch (err) {
    throw new Error(`${file}: ${(err as Error).message}`);
  }
  if (typeof fm.description !== 'string' || !fm.description.trim()) throw new Error(`${file}: description is empty`);
  return { name: typeof fm.name === 'string' ? fm.name : path.basename(dir), dir, description: fm.description };
}

/** A bundle folder holds one skill (SKILL.md at its root) or one skill per subfolder. */
export function bundleSkills(dir: string): Skill[] {
  if (!fs.existsSync(dir)) return [];
  if (fs.existsSync(path.join(dir, 'SKILL.md'))) return [parseSkill(dir)];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter((d) => d.isDirectory() && fs.existsSync(path.join(dir, d.name, 'SKILL.md')))
    .map((d) => parseSkill(path.join(dir, d.name)))
    .sort((a, b) => path.basename(a.dir).localeCompare(path.basename(b.dir)));
}

/** Every skill folder in a checkout: the root alone when it is a skill, else each outermost SKILL.md folder,
 *  first by shallowest path when a name repeats (repos often mirror skills under plugins/). */
export function findSkillDirs(root: string): string[] {
  if (fs.existsSync(path.join(root, 'SKILL.md'))) return [root];
  const found: string[] = [];
  const walk = (dir: string) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      if (!e.isDirectory() || SKIP.has(e.name) || e.name.startsWith('.')) continue;
      const sub = path.join(dir, e.name);
      if (fs.existsSync(path.join(sub, 'SKILL.md'))) found.push(sub);
      else walk(sub);
    }
  };
  walk(root);
  const byName = new Map<string, string>();
  for (const d of found.sort((a, b) => a.split(path.sep).length - b.split(path.sep).length || a.localeCompare(b))) {
    if (!byName.has(path.basename(d))) byName.set(path.basename(d), d);
  }
  return [...byName.values()];
}

const copy = (from: string, to: string) =>
  fs.cpSync(from, to, { recursive: true, filter: (src) => !SKIP.has(path.basename(src)) });

/** Replace vendor/<name> with every skill in the repo's default branch. Local edits are overwritten. */
export async function syncBundle(repo: Repo, name: string, b: Bundle): Promise<number> {
  const url = GITHUB_SLUG.test(b.repo!) ? `https://github.com/${b.repo}.git` : b.repo!;
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'my-skills-'));
  try {
    const clone = Bun.spawn(['git', 'clone', '--depth', '1', '--quiet', url, tmp], { stderr: 'pipe' });
    if ((await clone.exited) !== 0) throw new Error(`${name}: git clone ${url} failed: ${(await new Response(clone.stderr).text()).trim()}`);
    // A skill an agent cannot parse is unusable, so it is skipped rather than failing the whole bundle.
    const dirs = findSkillDirs(tmp).filter((d) => {
      try {
        parseSkill(d);
        return true;
      } catch (err) {
        console.warn(`⚠ ${name}: skipped ${path.relative(tmp, d) || '.'}: ${(err as Error).message.replace(`${path.join(d, 'SKILL.md')}: `, '')}`);
        return false;
      }
    });
    if (dirs.length === 0) throw new Error(`${name}: ${b.repo} has no usable SKILL.md`);
    // Staged beside vendor/ so the final rename stays on one filesystem.
    const staged = path.join(repo.vendorDir, `.${name}.staging`);
    fs.rmSync(staged, { recursive: true, force: true });
    fs.mkdirSync(repo.vendorDir, { recursive: true });
    if (dirs[0] === tmp) {
      copy(tmp, staged);
    } else {
      for (const d of dirs) copy(d, path.join(staged, path.basename(d)));
    }
    try {
      bundleSkills(staged); // validate before replacing
    } catch (err) {
      fs.rmSync(staged, { recursive: true, force: true });
      throw err;
    }
    const dest = bundleDir(repo, name, b);
    fs.rmSync(dest, { recursive: true, force: true });
    fs.renameSync(staged, dest);
    return dirs.length;
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

const cell = (s: string, max = 240) => {
  const t = s.replace(/\s+/g, ' ').trim();
  return (t.length <= max ? t : `${t.slice(0, max - 1).replace(/\s+\S*$/, '')}…`).replace(/\|/g, '\\|');
};

function routerText(name: string, description: string, intro: string, rows: string[], header: string): string {
  return [
    '---',
    `name: ${name}`,
    `description: ${JSON.stringify(description)}`,
    '---',
    '',
    '<!-- Generated by my-skills. Edit bundles.json or the source skills, then run ./run.sh -->',
    '',
    `# ${name}`,
    '',
    intro,
    '',
    header,
    header.replace(/[^|]+/g, ' --- '),
    ...rows,
    '',
  ].join('\n');
}

/** What an agent links for a bundle: a one-skill bundle's own folder, else its generated router. */
export function entryDir(repo: Repo, name: string, b: Bundle): string {
  const skills = bundleSkills(bundleDir(repo, name, b));
  return skills.length === 1 ? skills[0]!.dir : path.join(repo.buildDir, name);
}

/** Write routers for multi-skill bundles and find-skill for the gateway tier into outDir. */
export function build(repo: Repo, config: Config, outDir = repo.buildDir): void {
  fs.rmSync(outDir, { recursive: true, force: true });
  fs.mkdirSync(outDir, { recursive: true });
  const gateway: string[] = [];

  for (const [name, b] of Object.entries(config.bundles)) {
    const dir = bundleDir(repo, name, b);
    const skills = bundleSkills(dir);
    if (skills.length === 0) throw new Error(`${name}: no skills in ${path.relative(repo.root, dir)}${b.repo ? ' (run ./run.sh sync)' : ''}`);
    if (skills.length === 1 && skills[0]!.name !== name) {
      throw new Error(`${name}: its SKILL.md is named "${skills[0]!.name}"; rename the bundle to match`);
    }
    if (b.tier === 'gateway') gateway.push(`| ${name} | ${cell(b.summary)} | \`${path.join(entryDir(repo, name, b), 'SKILL.md')}\` |`);
    if (skills.length === 1) continue;

    // Members are copied with SKILL.md renamed to GUIDE.md, so agents that scan recursively see only the router.
    const out = path.join(outDir, name);
    const rows = skills.map((s) => {
      const id = path.basename(s.dir);
      copy(s.dir, path.join(out, id));
      fs.renameSync(path.join(out, id, 'SKILL.md'), path.join(out, id, 'GUIDE.md'));
      return `| [${id}](${id}/GUIDE.md) | ${cell(s.description)} |`;
    });
    fs.writeFileSync(path.join(out, 'SKILL.md'), routerText(
      name,
      `Use for ${b.summary}. Read only the guide the task needs.`,
      `${skills.length} guides. Read only the one the current task needs. Each guide's folder is its root for relative paths and scripts; "this SKILL.md" in a guide means its GUIDE.md, and a guide that names another skill of this bundle means that row here.`,
      rows,
      '| Guide | Use when |',
    ));
  }

  if (gateway.length) {
    const lines = Object.entries(config.bundles).filter(([, b]) => b.tier === 'gateway').map(([, b]) => b.summary).join('; ');
    const description = `Load an installed skill that is not listed. Use before saying no skill exists, and for: ${lines}.`;
    if (description.length > 1024) throw new Error(`${FINDER}: gateway summaries total ${description.length} chars (max 1024). Shorten them`);
    fs.mkdirSync(path.join(outDir, FINDER));
    fs.writeFileSync(path.join(outDir, FINDER, 'SKILL.md'), routerText(
      FINDER,
      description,
      'These skills are installed but not listed, to save context. Read the file of the one that fits the task and follow it as if it had been loaded as a skill.',
      gateway,
      '| Skill | Use for | Read |',
    ));
  }
}

/** Content, exec bits and symlink targets of a tree, for comparing a fresh build with what is on disk. */
export function treeHash(dir: string): string {
  const h = createHash('sha256');
  const walk = (d: string) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (e.isSymbolicLink()) h.update(`${path.relative(dir, p)}->${fs.readlinkSync(p)}`);
      else {
        h.update(path.relative(dir, p));
        h.update(String(fs.statSync(p).mode & 0o111));
        h.update(fs.readFileSync(p));
      }
    }
  };
  if (fs.existsSync(dir)) walk(dir);
  return h.digest('hex');
}

/** Links an agent should have: core bundles, plus find-skill when anything is in the gateway tier. */
export function desiredLinks(repo: Repo, config: Config): Map<string, string> {
  const out = new Map<string, string>();
  for (const [name, b] of Object.entries(config.bundles)) if (b.tier === 'core') out.set(name, entryDir(repo, name, b));
  if (Object.values(config.bundles).some((b) => b.tier === 'gateway')) out.set(FINDER, path.join(repo.buildDir, FINDER));
  return out;
}
