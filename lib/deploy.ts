import fs from 'node:fs';
import path from 'node:path';
import type { LocalState, Manifest } from './manifest';
import type { Repo } from './repo';
import type { SkillDir } from './skills';

export type State = 'on' | 'off' | 'hidden';
export interface Status {
  state: State;
  /** For hidden members: the superskill that hides them. */
  by?: string;
}

/** Members are always hidden; visibility is controlled at the bundle level. */
export function resolveState(manifest: Manifest, local: LocalState, skills: SkillDir[]): Map<string, Status> {
  const memberOf = new Map<string, string>();
  for (const [name, def] of Object.entries(manifest.superskills)) {
    for (const member of def.members) memberOf.set(member, name);
  }
  const disabled = new Set(local.disabled);
  return new Map(skills.map(skill => {
    const by = memberOf.get(skill.name);
    return [skill.name, by ? { state: 'hidden', by } : { state: disabled.has(skill.name) ? 'off' : 'on' }];
  }));
}

/** Name → folder for every skill an agent should see. */
export function activeSources(skills: SkillDir[], states: Map<string, Status>): Map<string, string> {
  return new Map(skills.filter(s => states.get(s.name)?.state === 'on').map(s => [s.name, s.abs]));
}

export interface Target {
  id?: string;
  name: string;
  dir: string;
}

export function agentTargets(home: string): Target[] {
  const at = (rel: string) => path.join(home, rel);
  return [
    { id: 'antigravity-cli', name: 'Antigravity CLI (Direct)', dir: at('.gemini/antigravity-cli/skills') },
    { id: 'antigravity', name: 'Antigravity (~/.antigravity)', dir: at('.antigravity/skills') },
    { id: 'gemini', name: 'Antigravity (~/.gemini/skills)', dir: at('.gemini/skills') },
    { id: 'codex', name: 'Codex CLI', dir: at('.codex/skills') },
    { id: 'claude', name: 'Claude Code', dir: at('.claude/skills') },
    { id: 'opencode', name: 'OpenCode', dir: at('.config/opencode/skills') },
    { id: 'cursor', name: 'Cursor', dir: at('.cursor/skills') },
    { id: 'agents', name: 'Universal Agents (~/.agents)', dir: at('.agents/skills') },
    { id: 'config-agents', name: 'Universal Agents (~/.config/agents)', dir: at('.config/agents/skills') },
  ];
}

export interface Plan {
  target: Target;
  create: string[];
  replace: string[];
  remove: string[];
  conflicts: string[];
  kept: number;
}

/** Only links pointing into this checkout belong to us. Foreign dangling links stay untouched. */
function isOurLink(resolved: string, repo: Repo): boolean {
  const r = path.resolve(resolved);
  if (r.startsWith(repo.skillsDir + path.sep) || r.startsWith(repo.superDir + path.sep) || r.startsWith(repo.sourcesDir + path.sep)) return true;
  return false;
}

function lstatOrNull(p: string): fs.Stats | null {
  try {
    return fs.lstatSync(p);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') return null;
    throw err;
  }
}

export function planTarget(target: Target, desired: Map<string, string>, repo: Repo): Plan {
  const plan: Plan = { target, create: [], replace: [], remove: [], conflicts: [], kept: 0 };

  for (const [name, src] of desired) {
    const dest = path.join(target.dir, name);
    const st = lstatOrNull(dest);
    if (!st) {
      plan.create.push(name);
    } else if (!st.isSymbolicLink()) {
      plan.conflicts.push(`${name}: a real file or folder is in the way at ${dest}`);
    } else {
      const resolved = path.resolve(target.dir, fs.readlinkSync(dest));
      if (resolved === path.resolve(src)) plan.kept++;
      else if (isOurLink(resolved, repo)) plan.replace.push(name);
      else plan.conflicts.push(`${name}: link to ${resolved} is not ours, left alone`);
    }
  }

  if (fs.existsSync(target.dir)) {
    for (const entry of fs.readdirSync(target.dir)) {
      if (desired.has(entry)) continue;
      const dest = path.join(target.dir, entry);
      const st = lstatOrNull(dest);
      if (st?.isSymbolicLink() && isOurLink(path.resolve(target.dir, fs.readlinkSync(dest)), repo)) {
        plan.remove.push(entry);
      }
    }
  }
  return plan;
}

export function applyPlan(plan: Plan, desired: Map<string, string>): void {
  const dir = plan.target.dir;
  fs.mkdirSync(dir, { recursive: true });
  for (const name of [...plan.create, ...plan.replace]) {
    const dest = path.join(dir, name);
    if (plan.replace.includes(name)) fs.unlinkSync(dest);
    fs.symlinkSync(desired.get(name)!, dest, process.platform === 'win32' ? 'junction' : 'dir');
  }
  for (const name of plan.remove) fs.unlinkSync(path.join(dir, name));
}

/** Read a JSON config (or start empty), apply an edit, and write only if something changed.
 *  Malformed JSON throws. It is never replaced with an empty object. */
async function editConfig(file: string, dryRun: boolean, label: string, edit: (cfg: any) => void): Promise<string> {
  const cfg = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
  if (!cfg || typeof cfg !== 'object' || Array.isArray(cfg)) throw new Error(`${label} config must be an object: ${file}`);
  const before = JSON.stringify(cfg);
  edit(cfg);
  if (JSON.stringify(cfg) === before) return `  ✓ ${label} config up to date: ${file}`;
  if (!dryRun) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(cfg, null, 2) + '\n');
  }
  return `  ✓ ${label} config ${dryRun ? 'would be updated' : 'updated'}: ${file}`;
}

/** Gemini and OpenCode read the repo's skills/ folder directly, which would bring disabled
 *  skills back. Point them at the active set instead. */
export async function registerActiveDir(repo: Repo, home: string, dryRun: boolean, targetIds: string[] = []): Promise<string[]> {
  const same = (p: unknown, dir: string) =>
    typeof p === 'string' && path.resolve(p.replace(/^~/, home)) === path.resolve(dir);

  const gemini = !targetIds.some(id => ['gemini', 'antigravity', 'antigravity-cli'].includes(id)) ? null : await editConfig(path.join(home, '.gemini/config/skills.json'), dryRun, 'Antigravity', (cfg) => {
    const entries: Array<{ path?: unknown }> = Array.isArray(cfg.entries) ? cfg.entries : [];
    const kept = entries.filter((e) => !same(e?.path, repo.skillsDir));
    if (!kept.some((e) => same(e?.path, repo.activeDir))) kept.push({ path: repo.activeDir });
    cfg.entries = kept;
  });

  const opencode = !targetIds.includes('opencode') ? null : await editConfig(path.join(home, '.config/opencode/opencode.json'), dryRun, 'OpenCode', (cfg) => {
    if (!cfg.$schema) cfg.$schema = 'https://opencode.ai/config.json';
    if (cfg.skills !== undefined && !Array.isArray(cfg.skills) && (!cfg.skills || typeof cfg.skills !== 'object')) throw new Error('OpenCode skills must be an object');
    const settings = Array.isArray(cfg.skills) ? { paths: cfg.skills } : (cfg.skills ?? {});
    if (settings.paths !== undefined && !Array.isArray(settings.paths)) throw new Error('OpenCode skills.paths must be an array');
    const paths: unknown[] = settings.paths ?? [];
    const kept = paths.filter((p) => !same(p, repo.skillsDir));
    if (!kept.some((p) => same(p, repo.activeDir))) kept.push(repo.activeDir);
    cfg.skills = { ...settings, paths: kept };
  });

  return [gemini, opencode].filter((line): line is string => line !== null);
}

export function planAll(repo: Repo, skills: SkillDir[], states: Map<string, Status>, home: string, targetIds: string[] = []) {
  const targets = agentTargets(home);
  for (const id of targetIds) if (!targets.some(t => t.id === id)) throw new Error(`unknown target: ${id}`);
  const desired = activeSources(skills, states);
  const plans = [
    planTarget({ name: 'active set', dir: repo.activeDir }, desired, repo),
    ...targets.filter(t => targetIds.includes(t.id!)).map((t) => planTarget(t, desired, repo)),
  ];
  return { desired, plans };
}

export async function deployGlobal(
  repo: Repo,
  skills: SkillDir[],
  states: Map<string, Status>,
  home: string,
  dryRun = false,
  targetIds: string[] = [],
): Promise<string[]> {
  const { desired, plans } = planAll(repo, skills, states, home, targetIds);
  const lines: string[] = [];

  // Preflight every target and config before changing any links.
  const configs = await registerActiveDir(repo, home, true, targetIds);
  const conflicts = plans.flatMap(p => p.conflicts.map(c => `${p.target.name}: ${c}`));
  if (conflicts.length && !dryRun) throw new Error(`Deployment conflicts:\n${conflicts.join('\n')}`);
  for (const plan of plans) {
    const changes = plan.create.length + plan.replace.length + plan.remove.length;
    if (!dryRun) applyPlan(plan, desired);
    lines.push(`  ${plan.conflicts.length ? '⚠' : '✓'} ${plan.target.name} (${plan.target.dir}): ` +
      `${plan.kept + plan.create.length + plan.replace.length} linked` +
      (changes ? ` (${plan.create.length} new, ${plan.replace.length} replaced, ${plan.remove.length} removed)` : '') +
      (dryRun ? ' [dry run]' : ''));
    for (const conflict of plan.conflicts) lines.push(`    ⚠ ${conflict}`);
  }
  lines.push(...(dryRun ? configs : await registerActiveDir(repo, home, false, targetIds)));

  return lines;
}

/** Problems between what should be linked and what is. Read-only. */
export function doctor(repo: Repo, skills: SkillDir[], states: Map<string, Status>, home: string, targetIds: string[] = []): string[] {
  const { plans } = planAll(repo, skills, states, home, targetIds);
  const issues = plans.flatMap((p) => [
    ...p.create.map((n) => `${n} is not linked in ${p.target.name}`),
    ...p.replace.map((n) => `${n} has a stale link in ${p.target.name}`),
    ...p.remove.map((n) => `${n} is still linked in ${p.target.name} but is disabled or gone`),
    ...p.conflicts.map((c) => `${c} (${p.target.name})`),
  ]);
  const same = (value: unknown, dir: string) => typeof value === 'string' && path.resolve(value.replace(/^~/, home)) === path.resolve(dir);
  const configs = [
    { ids: ['gemini', 'antigravity', 'antigravity-cli'], name: 'Antigravity', file: '.gemini/config/skills.json', paths: (cfg: any) => Array.isArray(cfg.entries) ? cfg.entries.map((e: any) => e?.path) : [] },
    { ids: ['opencode'], name: 'OpenCode', file: '.config/opencode/opencode.json', paths: (cfg: any) => Array.isArray(cfg.skills) ? cfg.skills : (Array.isArray(cfg.skills?.paths) ? cfg.skills.paths : []) },
  ];
  for (const config of configs) {
    if (!config.ids.some(id => targetIds.includes(id))) continue;
    try {
      const cfg = JSON.parse(fs.readFileSync(path.join(home, config.file), 'utf8'));
      const paths = config.paths(cfg);
      if (!paths.some((p: unknown) => same(p, repo.activeDir))) issues.push(`${config.name}: active set is not registered`);
      if (paths.some((p: unknown) => same(p, repo.skillsDir))) issues.push(`${config.name}: full library is still registered`);
    } catch (err) {
      issues.push(`${config.name}: cannot read config: ${(err as Error).message}`);
    }
  }
  return issues;
}
