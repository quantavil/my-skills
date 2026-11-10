import fs from 'node:fs';
import path from 'node:path';

/** core: linked into every agent. gateway: reached only through find-skill. */
export type Tier = 'core' | 'gateway';

export interface Bundle {
  /** owner/repo on GitHub, or a git URL or path. Absent: a local bundle in skills/<name>. */
  repo?: string;
  tier: Tier;
  /** What the bundle is for. Router description of multi-skill bundles; find-skill line for gateway ones. */
  summary: string;
}

export interface Config {
  /** Agent target IDs to deploy to (see lib/deploy.ts). */
  targets: string[];
  bundles: Record<string, Bundle>;
}

/** Every path the manager uses, from one root. */
export interface Repo {
  root: string;
  configPath: string;
  /** Local bundles. */
  skillsDir: string;
  /** Upstream bundles as synced. Per machine. */
  vendorDir: string;
  /** Generated routers and find-skill. Per machine. */
  buildDir: string;
  readmePath: string;
}

export function repoAt(root: string): Repo {
  return {
    root,
    configPath: path.join(root, 'bundles.json'),
    skillsDir: path.join(root, 'skills'),
    vendorDir: path.join(root, 'vendor'),
    buildDir: path.join(root, '.build'),
    readmePath: path.join(root, 'README.md'),
  };
}

export const FINDER = 'find-skill';
/** A repo field that is a GitHub owner/repo slug rather than a git URL or path. */
export const GITHUB_SLUG = /^[\w.-]+\/[\w.-]+$/;
const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/;

function bad(msg: string): never {
  throw new Error(`bundles.json: ${msg}`);
}

export function validateConfig(raw: any): Config {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) bad('expected an object');
  for (const key of Object.keys(raw)) if (key !== 'targets' && key !== 'bundles') bad(`unknown field ${key}`);
  const targets = raw.targets ?? [];
  if (!Array.isArray(targets) || !targets.every((t: unknown) => typeof t === 'string')) bad('targets must be a list of IDs');
  const bundles: Record<string, Bundle> = {};
  for (const [name, b] of Object.entries<any>(raw.bundles ?? {})) {
    if (!SLUG.test(name)) bad(`${name}: names use lowercase letters, digits and hyphens`);
    if (name === FINDER) bad(`${name} is reserved for the generated gateway router`);
    if (!b || typeof b !== 'object') bad(`${name}: expected an object`);
    for (const key of Object.keys(b)) if (!['repo', 'tier', 'summary'].includes(key)) bad(`${name}: unknown field ${key}`);
    if (b.repo !== undefined && (typeof b.repo !== 'string' || !b.repo)) bad(`${name}: repo must be a non-empty string`);
    if (b.tier !== 'core' && b.tier !== 'gateway') bad(`${name}: tier must be core or gateway`);
    if (typeof b.summary !== 'string' || !b.summary.trim()) bad(`${name}: summary is required`);
    bundles[name] = { ...(b.repo ? { repo: b.repo } : {}), tier: b.tier, summary: b.summary.trim() };
  }
  return { targets, bundles };
}

export function readConfig(repo: Repo): Config {
  if (!fs.existsSync(repo.configPath)) throw new Error(`missing ${repo.configPath}`);
  return validateConfig(JSON.parse(fs.readFileSync(repo.configPath, 'utf8')));
}

/** Where a bundle's skills live on disk. */
export function bundleDir(repo: Repo, name: string, b: Bundle): string {
  return path.join(b.repo ? repo.vendorDir : repo.skillsDir, name);
}
