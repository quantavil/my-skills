import fs from 'node:fs';
import path from 'node:path';
import type { Repo } from './repo';

export interface SkillDir {
  /** The folder name, which is also the link name agents see. */
  name: string;
  /** Logical source or generated bundle; source files may live in sources/. */
  root: 'skills' | 'superskills';
  abs: string;
  description: string;
  /** The name written in SKILL.md, when present. Verified to match the folder. */
  declared?: string;
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

/** Source skills and generated bundles. Names are unique across all three directories. */
export function listSkills(repo: Repo): SkillDir[] {
  const out: SkillDir[] = [];
  const seen = new Map<string, string>();

  for (const [root, base, entry] of [
    ['skills', repo.skillsDir, 'SKILL.md'],
    ['skills', repo.sourcesDir, 'GUIDE.md'],
    ['superskills', repo.superDir, 'SKILL.md'],
  ] as const) {
    if (!fs.existsSync(base)) continue;

    for (const d of fs.readdirSync(base, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const abs = path.join(base, d.name);
      const file = path.join(abs, entry);
      if (!d.isDirectory() || !fs.existsSync(file)) continue;

      const label = `${path.basename(base)}/${d.name}`;
      try {
        const { name, description } = parseFrontmatter(fs.readFileSync(file, 'utf8'));
        const prev = seen.get(d.name);
        if (prev) throw new Error(`two skills both named "${d.name}": ${prev} and ${label}`);
        seen.set(d.name, label);
        out.push({ name: d.name, root, abs, description: description ?? '', declared: name });
      } catch (e) {
        throw new Error(`${label}: ${(e as Error).message}`);
      }
    }
  }
  return out;
}

/** Resolve editable source paths after members have moved out of skills/. */
export function sourceDir(repo: Repo, name: string): string {
  const archived = path.join(repo.sourcesDir, name);
  return fs.existsSync(archived) ? archived : path.join(repo.skillsDir, name);
}

export function sourceEntry(dir: string): string {
  return path.join(dir, fs.existsSync(path.join(dir, 'SKILL.md')) ? 'SKILL.md' : 'GUIDE.md');
}
