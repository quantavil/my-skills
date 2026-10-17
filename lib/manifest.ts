import type { Repo } from './repo';

export const SKILL_TYPES = ['upstream', 'local', 'superskill'] as const;
export type SkillType = (typeof SKILL_TYPES)[number];

const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const SHA256 = /^[0-9a-f]{64}$/;

export interface SkillMeta {
  type: SkillType;
  /** Folder hash when the skill was last accepted. Upstream drift against it is an error. */
  contentHash: string;
}

export interface SuperDef {
  members: string[];
  description: string;
}

/** Committed. Holds what each skill is and how it is grouped. */
export interface Manifest {
  version: 1;
  skills: Record<string, SkillMeta>;
  superskills: Record<string, SuperDef>;
}

/** Per machine, not committed. Desktop and laptop can disagree about what is on. */
export interface LocalState {
  disabled: string[];
  /** Explicit agent target IDs. Empty means no global deployment. */
  targets?: string[];
}

export const emptyManifest = (): Manifest => ({ version: 1, skills: {}, superskills: {} });
export const emptyLocal = (): LocalState => ({ disabled: [] });

export function checkName(name: string): string {
  if (!SLUG.test(name)) throw new Error(`invalid name "${name}": use lowercase letters, digits and hyphens`);
  return name;
}

export function isSkillType(v: string): v is SkillType {
  return (SKILL_TYPES as readonly string[]).includes(v);
}

function bad(msg: string): never {
  throw new Error(`skills.json: ${msg}`);
}

function fields(value: object, allowed: string[], name: string): void {
  for (const key of Object.keys(value)) if (!allowed.includes(key)) bad(`${name}: unknown field ${key}`);
}

const isStrings = (v: unknown): v is string[] => Array.isArray(v) && v.every((x) => typeof x === 'string');

/** Unknown fields, types and hashes are errors, not defaults: a hand-edited file should fail loudly. */
export function validateManifest(raw: unknown): Manifest {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) bad('expected a JSON object');
  const r = raw as Record<string, unknown>;
  if (r.version !== 1) bad('unsupported version');

  for (const key of ['skills', 'superskills']) {
    const value = r[key];
    if (value !== undefined && (!value || typeof value !== 'object' || Array.isArray(value))) bad(`${key}: expected an object`);
  }
  const skills: Record<string, SkillMeta> = {};
  for (const [name, v] of Object.entries((r.skills ?? {}) as Record<string, unknown>)) {
    checkName(name);
    const m = (v ?? {}) as Partial<SkillMeta>;
    if (typeof m.type !== 'string' || !isSkillType(m.type)) bad(`${name}: type must be upstream, local or superskill`);
    fields(m, ['type', 'contentHash'], name);
    if (typeof m.contentHash !== 'string' || !SHA256.test(m.contentHash)) bad(`${name}: contentHash must be a sha256 hex string`);
    skills[name] = { type: m.type, contentHash: m.contentHash };
  }

  const superskills: Record<string, SuperDef> = {};
  for (const [name, v] of Object.entries((r.superskills ?? {}) as Record<string, unknown>)) {
    checkName(name);
    const d = (v ?? {}) as Partial<SuperDef>;
    if (!isStrings(d.members) || d.members.length === 0) bad(`${name}: members must be a non-empty list`);
    fields(d, ['members', 'description'], name);
    if (typeof d.description !== 'string') bad(`${name}: description must be a string`);
    for (const member of d.members) checkName(member);
    if (new Set(d.members).size !== d.members.length) bad(`${name}: duplicate members`);
    superskills[name] = { members: d.members, description: d.description };
  }

  return { version: 1, skills, superskills };
}

export async function readManifest(repo: Repo): Promise<Manifest | null> {
  const file = Bun.file(repo.manifestPath);
  if (!(await file.exists())) return null;
  return validateManifest(JSON.parse(await file.text()));
}

export async function writeManifest(repo: Repo, m: Manifest): Promise<void> {
  const sorted = <T>(o: Record<string, T>) => Object.fromEntries(Object.keys(o).sort().map((k) => [k, o[k]]));
  const out = { version: 1, skills: sorted(m.skills), superskills: sorted(m.superskills) };
  await Bun.write(repo.manifestPath, JSON.stringify(out, null, 2) + '\n');
}

export async function readLocal(repo: Repo): Promise<LocalState> {
  const file = Bun.file(repo.localPath);
  if (!(await file.exists())) return emptyLocal();
  const raw = JSON.parse(await file.text()) as Partial<LocalState>;
  const disabled = raw.disabled ?? [];
  if (!isStrings(disabled)) throw new Error('skills.local.json: disabled must be a list of names');
  if (raw.targets !== undefined && !isStrings(raw.targets)) throw new Error('skills.local.json: targets must be a list of IDs');
  return { disabled, ...(raw.targets !== undefined ? { targets: raw.targets } : {}) };
}

export async function writeLocal(repo: Repo, s: LocalState): Promise<void> {
  const out = { disabled: [...new Set(s.disabled)].sort(), ...(s.targets !== undefined ? { targets: [...new Set(s.targets)].sort() } : {}) };
  await Bun.write(repo.localPath, JSON.stringify(out, null, 2) + '\n');
}
