#!/usr/bin/env bun
// ./run.sh                       rebuild local bundles and README (never deploys)
// ./run.sh add [owner/repo]       import upstream skills or create local skills / bundles
// ./run.sh sync [--force]         update upstream skills; local customizations are excluded
// ./run.sh set name --accept     preserve an upstream edit as a local skill
// ./run.sh superskill name --members a,b --description "Use for ..."
// ./run.sh enable|disable name   save visibility preferences; deploy separately
// ./run.sh targets [codex claude ... | none]   inspect or select deployment targets
// ./run.sh deploy [--dry-run]     apply selected visibility to selected targets
// ./run.sh status|context|doctor|check         inspect without writing
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { sourceHash, hashFiles } from './lib/hash';
import {
  checkName,
  emptyManifest,
  isSkillType,
  readLocal,
  readManifest,
  writeLocal,
  writeManifest,
  SKILL_TYPES,
  type Manifest,
  type SkillType,
  type SuperDef,
} from './lib/manifest';
import { repoAt } from './lib/repo';
import { parseFrontmatter, listSkills, sourceDir, sourceEntry } from './lib/skills';
import { buildSuperFiles, resolveMembers, writeSuper } from './lib/superskill';
import { addArgs, readLock, writeLock, resolveNames, runSkills, type Lock } from './lib/upstream';
import { agentTargets, deployGlobal, doctor, resolveState } from './lib/deploy';
import { reindex, readmeMatches } from './lib/reindex';
import { verify } from './lib/verify';

const REPO = repoAt(import.meta.dirname);
const HOME = os.homedir();

export interface Parsed {
  pos: string[];
  opts: Map<string, string | true>;
  skills: string[];
}

const VALUE_FLAGS = new Set(['type', 'name', 'description', 'members']);
const BOOLEAN_FLAGS = new Set(['force', 'dry-run', 'accept']);

/** `-s` repeats. `--name value` takes a value. Everything else is positional. */
export function parseArgs(argv: string[]): Parsed {
  const out: Parsed = { pos: [], opts: new Map(), skills: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]!;
    if (a === '-s' || a === '--skill') {
      const v = argv[++i];
      if (!v || v.startsWith('-')) throw new Error(`${a} needs a skill name`);
      out.skills.push(v);
    } else if (a.startsWith('--')) {
      const key = a.slice(2);
      if (!BOOLEAN_FLAGS.has(key) && !VALUE_FLAGS.has(key)) throw new Error(`unknown option --${key}`);
      if (BOOLEAN_FLAGS.has(key)) {
        out.opts.set(key, true);
      } else {
        const v = argv[++i];
        if (v === undefined || v.startsWith('--')) throw new Error(`--${key} needs a value`);
        out.opts.set(key, v);
      }
    } else {
      out.pos.push(a);
    }
  }
  return out;
}

const str = (p: Parsed, key: string): string | undefined => {
  const v = p.opts.get(key);
  return typeof v === 'string' ? v : undefined;
};
const flag = (p: Parsed, key: string): boolean => p.opts.has(key);
const list = (s?: string): string[] => (s ?? '').split(',').map((x) => x.trim()).filter(Boolean);

async function requireManifest(): Promise<Manifest> {
  const m = await readManifest(REPO);
  if (!m) throw new Error('skills.json is missing: run bun index.ts first');
  return m;
}

/** Derived state first, then print anything still out of step. */
async function refresh(): Promise<void> {
  for (const line of await reindex(REPO)) console.log(`  ${line}`);
  const problems = verify(REPO, listSkills(REPO), await readLock(REPO), await readManifest(REPO));
  if (problems.length) throw new Error(problems.join('\n'));
}

async function deployNow(dryRun = false): Promise<void> {
  const skills = listSkills(REPO);
  const manifest = (await readManifest(REPO)) ?? emptyManifest();
  const local = await readLocal(REPO);
  const states = resolveState(manifest, local, skills);
  console.log(`\n🚀 ${dryRun ? 'Planning' : 'Deploying'} the active set to selected AI agent targets...`);
  for (const line of await deployGlobal(REPO, skills, states, HOME, dryRun, local.targets ?? [])) console.log(line);
  console.log('');
}

/** Stamp fresh hashes onto skills, so skills.json records what was accepted. */
function record(m: Manifest, names: string[], meta: { type: SkillType }): void {
  for (const n of names) {
    m.skills[n] = { ...meta, contentHash: sourceHash(sourceDir(REPO, n)) };
  }
}

async function scaffoldLocal(p: Parsed): Promise<string> {
  const name = checkName(str(p, 'name') ?? '');
  const description = (str(p, 'description') ?? '').trim();
  const text = `---\nname: ${name}\ndescription: ${JSON.stringify(description)}\n---\n\n# ${name}\n\n`;
  parseFrontmatter(text);
  const dir = path.join(REPO.skillsDir, name);
  if (listSkills(REPO).some(s => s.name === name)) throw new Error(`skill or bundle ${name} already exists`);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'SKILL.md'), text);
  return name;
}

/** Vendors from a repo and reports the installed names, including unchanged re-imports. */
async function vendorRepo(source: string, picks: string[], force = false): Promise<string[]> {
  const before = await readLock(REPO);
  const names = await runSkills(REPO, addArgs([source, ...picks.flatMap((s) => ['-s', s])]), force);
  const after = await readLock(REPO);
  for (const n of names) {
    const old = before[n];
    if (old && old.source !== after[n]?.source) {
      console.warn(`⚠ "${n}" was replaced: ${old.source} → ${after[n]?.source}`);
    }
  }
  return names;
}

async function cmdAdd(p: Parsed): Promise<void> {
  const type = str(p, 'type') ?? 'upstream';
  if (!isSkillType(type)) throw new Error(`--type must be one of: ${SKILL_TYPES.join(', ')}`);
  if (type === 'superskill') return cmdSuperskill(p);
  const target = p.pos[0] ?? '';
  if (!target && type !== 'local') throw new Error('usage: bun index.ts add <owner/repo> [-s name], or add --type local --name name --description "Use for ..."');
  if (!target && (!str(p, 'name') || !str(p, 'description'))) throw new Error('local creation needs --name and --description');
  const manifest = (await readManifest(REPO)) ?? emptyManifest();

  if (target === '') {
    record(manifest, [await scaffoldLocal(p)], { type: 'local' });
  } else {
    const names = await vendorRepo(target, p.skills, flag(p, 'force'));
    record(manifest, names, { type });
  }

  await writeManifest(REPO, manifest);
  await refresh();
}

async function cmdRemove(p: Parsed): Promise<void> {
  if (p.pos.length === 0) throw new Error('usage: bun index.ts remove <skill|repo|superskill>...');
  const manifest = await requireManifest();
  const lock = await readLock(REPO);

  const supers = p.pos.filter((n) => manifest.superskills[n]);
  const plain = p.pos.filter((n) => !manifest.superskills[n]);
  const names = plain.length ? resolveNames(plain, lock) : [];

  for (const n of names) {
    const owner = Object.keys(manifest.superskills).find((sup) => !supers.includes(sup) && manifest.superskills[sup]!.members.includes(n));
    if (owner) throw new Error(`${n} is a member of superskill "${owner}". Remove the superskill, or edit its members`);
  }

  for (const s of supers) {
    fs.rmSync(path.join(REPO.superDir, s), { recursive: true, force: true });
    delete manifest.superskills[s];
    delete manifest.skills[s];
    console.log(`removed superskill "${s}"`);
  }
  if (names.length) {
    console.log(`removing ${names.length}: ${names.join(', ')}`);
    for (const n of names) delete lock[n];
    await writeLock(REPO, lock);
    for (const n of names) {
      fs.rmSync(sourceDir(REPO, n), { recursive: true, force: true });
      delete manifest.skills[n];
    }
  }

  await writeManifest(REPO, manifest);
  await refresh();
}

async function cmdSync(p: Parsed): Promise<void> {
  let manifest = await requireManifest();
  const lock = await readLock(REPO);

  const drifted = Object.entries(manifest.skills)
    .filter(([n, m]) => m.type === 'upstream' && fs.existsSync(sourceDir(REPO, n)))
    .filter(([n, m]) => sourceHash(sourceDir(REPO, n)) !== m.contentHash)
    .map(([n]) => n);
  if (drifted.length && !flag(p, 'force')) {
    throw new Error(
      `vendored skills were edited locally: ${drifted.join(', ')}. ` +
        'Keep an edit with: bun index.ts set <name> --accept. Or pass --force to overwrite.',
    );
  }

  const names = Object.keys(manifest.skills).filter((n) => manifest.skills[n]?.type === 'upstream' && lock[n]);
  if (names.length === 0) return console.log('no upstream skills to sync');

  // One CLI call per repo. A repo contributing 14 skills would otherwise be fetched 14 times.
  const byRepo = new Map<string, string[]>();
  for (const n of names) {
    const entry = lock[n]!;
    const src = entry.sourceUrl ?? entry.source;
    byRepo.set(src, [...(byRepo.get(src) ?? []), n]);
  }

  const changed: string[] = [];
  for (const [src, group] of byRepo) {
    console.log(`\n↻ ${src}  (${group.length} skill${group.length > 1 ? 's' : ''})`);
    await runSkills(REPO, addArgs([src, ...group.flatMap((n) => ['-s', n])]), flag(p, 'force'));
    // Accept each successful repo before fetching the next, so a later failure is retryable.
    for (const n of group) {
      const h = sourceHash(sourceDir(REPO, n));
      if (h !== manifest.skills[n]!.contentHash) changed.push(n);
      manifest.skills[n]!.contentHash = h;
    }
    await writeManifest(REPO, manifest);
    for (const line of await reindex(REPO)) console.log(`  ${line}`);
    // Other repos may still have edits pending replacement by --force. Verify after all batches.
    manifest = await requireManifest();
  }
  console.log(changed.length ? `changed upstream: ${changed.join(', ')}` : 'no upstream changes');
  await refresh();
}

async function cmdSet(p: Parsed): Promise<void> {
  const [name] = p.pos;
  if (!name) throw new Error('usage: bun index.ts set <skill> [--type upstream|local] [--accept]');
  const manifest = await requireManifest();
  const meta = manifest.skills[name];
  if (!meta) throw new Error(`"${name}" is not a known skill`);
  const isSuper = meta.type === 'superskill';

  const type = str(p, 'type');
  if (type !== undefined) {
    if (isSuper) throw new Error(`"${name}" is a superskill. Change its members with: bun index.ts superskill ${name} ...`);
    if (!type || !isSkillType(type) || type === 'superskill') throw new Error('--type must be upstream or local');
    meta.type = type;
  }
  if (flag(p, 'accept')) {
    if (isSuper) throw new Error(`${name} is rebuilt from its members, so there is nothing to accept`);
    const h = sourceHash(sourceDir(REPO, name));
    console.log(`accepted ${name}: ${meta.contentHash.slice(0, 12)} → ${h.slice(0, 12)}`);
    meta.contentHash = h;
    meta.type = 'local';
  }

  await writeManifest(REPO, manifest);
  await refresh();
}

async function cmdSuperskill(p: Parsed): Promise<void> {
  const name = checkName(p.pos[0] ?? '');
  const manifest = (await readManifest(REPO)) ?? emptyManifest();
  const skills = listSkills(REPO);
  if (skills.some((s) => s.name === name && s.root === 'skills')) {
    throw new Error(`"${name}" is already a skill in skills/. Pick another name`);
  }

  const asked = list(str(p, 'members'));
  if (!asked.length) throw new Error('usage: bun index.ts superskill <name> --members <names-or-repo> [--description "Use for ..."]');
  // owner/repo expands to every skill vendored from that source.
  const members = resolveNames(asked, await readLock(REPO));
  const def: SuperDef = { members, description: (str(p, 'description') ?? '').trim() };
  const resolved = resolveMembers(skills, members, name);
  const files = buildSuperFiles(name, def, resolved);
  writeSuper(REPO, name, files);

  manifest.superskills[name] = def;
  manifest.skills[name] = {
    type: 'superskill',
    contentHash: hashFiles(files),
  };
  await writeManifest(REPO, manifest);
  console.log(`✓ superskill "${name}" built from ${members.join(', ')}`);
  await refresh();
}

async function cmdToggle(p: Parsed, on: boolean): Promise<void> {
  if (p.pos.length === 0) throw new Error(`usage: bun index.ts ${on ? 'enable' : 'disable'} <skill|superskill>...`);
  const manifest = await requireManifest();
  const local = await readLocal(REPO);
  const disabled = new Set(local.disabled);
  for (const t of p.pos) {
    if (!manifest.skills[t]) throw new Error(`unknown skill: ${t}`);
    const owner = Object.entries(manifest.superskills).find(([, def]) => def.members.includes(t))?.[0];
    if (owner) throw new Error(`${t} is bundled in ${owner}; enable or disable ${owner} instead`);
    if (on) disabled.delete(t);
    else disabled.add(t);
  }
  await writeLocal(REPO, { ...local, disabled: [...disabled] });
}

async function cmdStatus(): Promise<void> {
  const skills = listSkills(REPO);
  const manifest = (await readManifest(REPO)) ?? emptyManifest();
  const states = resolveState(manifest, await readLocal(REPO), skills);

  const badge = { on: '[on ]', off: '[off]', hidden: '[hid]' } as const;
  for (const s of skills.sort((a, b) => a.name.localeCompare(b.name))) {
    const st = states.get(s.name)!;
    const kind = s.root === 'superskills' ? 'superskill' : (manifest.skills[s.name]?.type ?? 'unlisted');
    const note = st.state === 'hidden' ? `  (member of ${st.by})` : '';
    console.log(`  ${badge[st.state]} ${s.name.padEnd(28)} ${kind}${note}`);
  }
}

async function cmdDeploy(p: Parsed): Promise<void> {
  const dryRun = flag(p, 'dry-run');
  if (!dryRun) await refresh();
  else {
    const problems = verify(REPO, listSkills(REPO), await readLock(REPO), await readManifest(REPO));
    if (problems.length) throw new Error(problems.join('\n'));
  }
  await deployNow(dryRun);
}

async function cmdDoctor(): Promise<void> {
  const skills = listSkills(REPO);
  const manifest = (await readManifest(REPO)) ?? emptyManifest();
  const local = await readLocal(REPO);
  const states = resolveState(manifest, local, skills);
  const issues = [...verify(REPO, skills, await readLock(REPO), manifest), ...doctor(REPO, skills, states, HOME, local.targets ?? [])];
  if (issues.length === 0) return console.log('✓ managed links and registrations match the selected targets');
  for (const issue of issues) console.error(`✗ ${issue}`);
  console.error(`\n${issues.length} problem(s). Run: bun index.ts deploy`);
  process.exitCode = 1;
}

async function cmdCheck(): Promise<void> {
  const skills = listSkills(REPO);
  const lock: Lock = await readLock(REPO);
  const manifest = await readManifest(REPO);
  const problems = verify(REPO, skills, lock, manifest);
  if (manifest && !(await readmeMatches(REPO, skills, lock, manifest))) {
    problems.push('README.md is stale (run bun index.ts)');
  }
  if (problems.length) {
    for (const p of problems) console.error(`✗ ${p}`);
    process.exit(1);
  }
  console.log(`✓ ${skills.length} skills verified`);
}

async function main(): Promise<void> {
  const [cmd = '', ...rest] = Bun.argv.slice(2);
  const p = parseArgs(rest);

  switch (cmd) {
    case '':
      return refresh();
    case 'context': {
      const skills = listSkills(REPO);
      const manifest = (await readManifest(REPO)) ?? emptyManifest();
      const states = resolveState(manifest, await readLocal(REPO), skills);
      const visible = skills.filter(s => states.get(s.name)!.state === 'on');
      const plain = skills.filter(s => s.root === 'skills');
      const bytes = (text: string) => Buffer.byteLength(text, 'utf8');
      console.log(`${plain.length} source skills; ${visible.length} discoverable entries (${visible.filter(s => s.root === 'superskills').length} bundles).`);
      console.log(`Description text: ${visible.reduce((n, s) => n + bytes(s.description), 0)} bytes; unbundled library: ${plain.reduce((n, s) => n + bytes(s.description), 0)} bytes.`);
      for (const s of visible.filter(s => s.root === 'superskills')) {
        const def = manifest.superskills[s.name]!;
        const router = fs.statSync(path.join(s.abs, 'SKILL.md')).size;
        const memberBytes = resolveMembers(skills, def.members, s.name).reduce((n, m) => n + fs.statSync(sourceEntry(m.abs)).size, 0);
        console.log(`  ${s.name}: ${router} bytes router; ${memberBytes} bytes of member instructions loaded only as needed`);
      }
      return;
    }
    case 'targets': {
      const local = await readLocal(REPO);
      const targets = agentTargets(HOME);
      if (p.pos.length) {
        const ids = p.pos[0] === 'none' ? [] : p.pos;
        if (p.pos.includes('none') && p.pos.length !== 1) throw new Error('use targets none by itself');
        for (const id of ids) if (!targets.some(t => t.id === id)) throw new Error(`unknown target: ${id}`);
        await writeLocal(REPO, { ...local, targets: ids });
        console.log('Targets saved. Run deploy --dry-run, then deploy to apply.');
      } else {
        for (const t of targets) console.log(`${(local.targets ?? []).includes(t.id!) ? '[on ]' : '[off]'} ${t.id}: ${t.dir}`);
      }
      return;
    }
    case 'add':
      return cmdAdd(p);
    case 'remove':
      return cmdRemove(p);
    case 'sync':
      return cmdSync(p);
    case 'set':
      return cmdSet(p);
    case 'superskill':
      return cmdSuperskill(p);
    case 'enable':
      return cmdToggle(p, true);
    case 'disable':
      return cmdToggle(p, false);
    case 'status':
      return cmdStatus();
    case 'deploy':
      return cmdDeploy(p);
    case 'doctor':
      return cmdDoctor();
    case 'check':
      return cmdCheck();
    default:
      throw new Error(`unknown command "${cmd}". See the usage at the top of index.ts`);
  }
}

// Only run when executed directly, so tests can import the helpers without side effects.
if (import.meta.main) {
  try {
    await main();
  } catch (e) {
    console.error(`✗ ${(e as Error).message}`);
    process.exit(1);
  }
}
