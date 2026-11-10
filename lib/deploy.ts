import fs from 'node:fs';
import path from 'node:path';
import type { Repo } from './config';

export interface Target {
  id: string;
  dir: string;
}

export function agentTargets(home: string): Target[] {
  return [
    ['claude', '.claude/skills'],
    ['codex', '.codex/skills'],
    ['opencode', '.config/opencode/skills'],
    ['cursor', '.cursor/skills'],
    ['gemini', '.gemini/skills'],
    ['antigravity', '.antigravity/skills'],
    ['antigravity-cli', '.gemini/antigravity-cli/skills'],
    ['agents', '.agents/skills'],
    ['config-agents', '.config/agents/skills'],
  ].map(([id, rel]) => ({ id: id!, dir: path.join(home, rel!) }));
}

export interface Plan {
  target: Target;
  create: string[];
  replace: string[];
  remove: string[];
  conflicts: string[];
  kept: number;
}

const lstat = (p: string) => fs.lstatSync(p, { throwIfNoEntry: false });

/** Plan one target. Only links into this repo are ours to replace or remove; anything else is left alone. */
export function planTarget(repo: Repo, target: Target, desired: Map<string, string>): Plan {
  const plan: Plan = { target, create: [], replace: [], remove: [], conflicts: [], kept: 0 };
  const ours = (p: string) => p.startsWith(repo.root + path.sep);
  const linkOf = (dest: string) => path.resolve(path.dirname(dest), fs.readlinkSync(dest));

  for (const [name, src] of desired) {
    const dest = path.join(target.dir, name);
    const st = lstat(dest);
    if (!st) plan.create.push(name);
    else if (!st.isSymbolicLink()) plan.conflicts.push(`${name}: a real file or folder is in the way at ${dest}`);
    else if (linkOf(dest) === src) plan.kept++;
    else if (ours(linkOf(dest))) plan.replace.push(name);
    else plan.conflicts.push(`${name}: link to ${linkOf(dest)} is not ours, left alone`);
  }
  if (fs.existsSync(target.dir)) {
    for (const name of fs.readdirSync(target.dir)) {
      const dest = path.join(target.dir, name);
      if (!desired.has(name) && lstat(dest)?.isSymbolicLink() && ours(linkOf(dest))) plan.remove.push(name);
    }
  }
  return plan;
}

/** Plan every selected target, and apply unless dryRun. Conflicts stop a real deploy before anything changes. */
export function deploy(repo: Repo, home: string, targetIds: string[], desired: Map<string, string>, dryRun: boolean): string[] {
  const all = agentTargets(home);
  for (const id of targetIds) if (!all.some((t) => t.id === id)) throw new Error(`unknown target: ${id}`);
  const plans = all.filter((t) => targetIds.includes(t.id)).map((t) => planTarget(repo, t, desired));
  const conflicts = plans.flatMap((p) => p.conflicts.map((c) => `${p.target.id}: ${c}`));
  if (conflicts.length && !dryRun) throw new Error(`deploy conflicts:\n${conflicts.join('\n')}`);

  return plans.flatMap((p) => {
    if (!dryRun) {
      fs.mkdirSync(p.target.dir, { recursive: true });
      for (const name of [...p.replace, ...p.remove]) fs.unlinkSync(path.join(p.target.dir, name));
      for (const name of [...p.create, ...p.replace]) fs.symlinkSync(desired.get(name)!, path.join(p.target.dir, name), 'dir');
    }
    const changes = [p.create.length && `${p.create.length} new`, p.replace.length && `${p.replace.length} replaced`, p.remove.length && `${p.remove.length} removed`].filter(Boolean);
    return [
      `${p.conflicts.length ? '⚠' : '✓'} ${p.target.id} (${p.target.dir}): ${desired.size - p.conflicts.length} linked${changes.length ? ` (${changes.join(', ')})` : ''}${dryRun ? ' [dry run]' : ''}`,
      ...p.conflicts.map((c) => `    ⚠ ${c}`),
    ];
  });
}
