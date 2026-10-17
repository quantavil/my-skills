import path from 'node:path';
import { filesMatch, sourceHash, hashFiles } from './hash';
import type { Manifest } from './manifest';
import type { Repo } from './repo';
import { buildSuperFiles, resolveMembers } from './superskill';
import type { SkillDir } from './skills';
import type { Lock } from './upstream';

/** Read-only. Lists everything that is out of step with skills.json, the lock and the disk. */
export function verify(repo: Repo, skills: SkillDir[], lock: Lock, manifest: Manifest | null): string[] {
  if (!manifest) return ['skills.json is missing: run bun index.ts'];

  const problems: string[] = [];
  const onDisk = new Map(skills.map((s) => [s.name, s]));

  for (const s of skills) {
    if (!manifest.skills[s.name]) problems.push(`${s.name}: not in skills.json (run bun index.ts)`);
    if (s.root === 'skills' && !lock[s.name]) problems.push(`${s.name}: not pinned in skills-lock.json (run bun index.ts)`);
    if (s.root === 'skills' && s.abs.startsWith(repo.skillsDir + path.sep) && Object.values(manifest.superskills).some(def => def.members.includes(s.name))) problems.push(`${s.name}: bundled member leaked into skills/ (run bun index.ts)`);
    if (s.declared && s.declared !== s.name) problems.push(`${s.root}/${s.name}: SKILL.md says name "${s.declared}"`);
    if (s.root === 'superskills' && !manifest.superskills[s.name]) {
      problems.push(`${s.name}: superskill folder has no definition in skills.json`);
    }
  }

  for (const [name, meta] of Object.entries(manifest.skills)) {
    const s = onDisk.get(name);
    if (!s) {
      problems.push(`${name}: in skills.json but has no folder (run bun index.ts)`);
      continue;
    }
    if (meta.type === 'superskill') {
      if (s.root !== 'superskills') problems.push(`${name}: superskills must live in superskills/`);
      continue;
    }
    if (s.root !== 'skills') problems.push(`${name}: ${meta.type} skills must live in skills/`);

    const h = sourceHash(s.abs);
    if (h !== meta.contentHash) {
      problems.push(
        meta.type === 'upstream'
          ? `${name}: vendored skill changed on disk. Revert it, or keep the change with: bun index.ts set ${name} --accept`
          : `${name}: local skill changed since the last index (run bun index.ts)`,
      );
    }
  }

  for (const [name, def] of Object.entries(manifest.superskills)) {
    try {
      const members = resolveMembers(skills, def.members, name);
      const files = buildSuperFiles(name, def, members);
      const built = hashFiles(files);
      const dir = path.join(repo.superDir, name);
      if (!filesMatch(dir, files)) {
        problems.push(`${name}: superskill is stale or was hand-edited (run bun index.ts)`);
      }
      if (manifest.skills[name]?.contentHash !== built) problems.push(`${name}: skills.json hash is stale (run bun index.ts)`);
    } catch (e) {
      problems.push(`${name}: ${(e as Error).message}`);
    }
  }

  return problems;
}
