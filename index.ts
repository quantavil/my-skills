#!/usr/bin/env bun
// Manages the vendored skill collection and keeps README.md's table in sync.
//   bun run add <repo> [-s <skill>...]   vendor a repo's skills, all of them by default
//   bun run remove <skill|repo>...       drop skills, by name or by upstream repo
//   bun run sync                         refetch everything at latest upstream
//   bun run check                        exit 1 if README.md is stale (CI)
//   bun run test                         asserts
//   bun index.ts                         rebuild the table

// `openclaw` is the one agent whose project dir is a plain `skills/` rather than a
// dotfolder, so it is used purely as a path selector — nothing OpenClaw-specific.
const AGENT = 'openclaw';
const SKILLS_DIR = `${import.meta.dir}/skills`;
const LOCK = `${import.meta.dir}/skills-lock.json`;
const README = `${import.meta.dir}/README.md`;
const START = '<!-- skills:start -->';
const END = '<!-- skills:end -->';
const UNSOURCED = 'Unsourced';

interface LockEntry {
  source: string;
  sourceUrl?: string;
}
type Lock = Record<string, LockEntry>;
interface Skill {
  name: string;
  dir: string;
  description: string;
}

/** Pull the YAML frontmatter block out of a SKILL.md. */
export function parseFrontmatter(text: string): { name?: string; description?: string } {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) throw new Error('no YAML frontmatter');
  return (Bun.YAML.parse(m[1]) ?? {}) as { name?: string; description?: string };
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
    const fromRepo = Object.keys(lock).filter((n) => lock[n].source === arg || lock[n].sourceUrl === arg);
    if (!fromRepo.length) unmatched.push(arg);
    for (const n of fromRepo) out.add(n);
  }

  if (unmatched.length) throw new Error(`not in this collection: ${unmatched.join(', ')}`);
  return [...out];
}

/** Missing lock is fine — a malformed one is not, so only absence is defaulted. */
const readLock = async (): Promise<Lock> => {
  const file = Bun.file(LOCK);
  if (!(await file.exists())) return {};
  return ((await file.json()) as { skills?: Lock }).skills ?? {};
};

function run(args: string[]) {
  const { exitCode } = Bun.spawnSync(['bunx', 'skills', ...args], { stdout: 'inherit', stderr: 'inherit' });
  if (exitCode !== 0) throw new Error(`skills ${args.join(' ')} failed`);
}

async function readSkills(): Promise<Skill[]> {
  const files = await Array.fromAsync(new Bun.Glob('*/SKILL.md').scan({ cwd: SKILLS_DIR }));
  return Promise.all(
    files.map(async (rel) => {
      const dir = rel.split('/')[0];
      try {
        const { name, description } = parseFrontmatter(await Bun.file(`${SKILLS_DIR}/${rel}`).text());
        return { name: name ?? dir, dir, description: description ?? '' };
      } catch (e) {
        throw new Error(`skills/${rel}: ${(e as Error).message}`);
      }
    }),
  );
}

/** Refetch every locked skill at its latest upstream commit. `skills update` is not
 *  used: it has no --agent flag, so it re-detects agents, scatters copies into
 *  .agents/ and .claude/, and leaves skills/ stale. */
async function sync() {
  const lock = await readLock();
  const names = Object.keys(lock);
  if (!names.length) return console.log('nothing in skills-lock.json yet');

  // One `add` per repo, not per skill — a repo contributing 14 skills would
  // otherwise be fetched 14 times.
  const byRepo = new Map<string, string[]>();
  for (const n of names) {
    const src = lock[n].sourceUrl ?? lock[n].source;
    byRepo.get(src)?.push(n) ?? byRepo.set(src, [n]);
  }

  for (const [src, group] of byRepo) {
    console.log(`\n↻ ${src}  (${group.length} skill${group.length > 1 ? 's' : ''})`);
    run(addArgs([src, ...group.flatMap((n) => ['-s', n])]));
  }
}

async function reindex(check = false) {
  const before = await Bun.file(README).text();
  const skills = await readSkills();
  const after = render(before, buildMarkdown(skills, await readLock()));

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

  console.log('selftest ok');
}

async function main() {
  const [cmd, ...rest] = Bun.argv.slice(2);

  switch (cmd) {
    case 'add': {
      if (!rest.length) throw new Error('usage: bun run add <repo> [-s <skill>...]');
      const before = await readLock();
      run(addArgs(rest));
      const after = await readLock();
      for (const [name, e] of Object.entries(after)) {
        if (before[name] && before[name].source !== e.source) {
          console.warn(`⚠ "${name}" was replaced: ${before[name].source} → ${e.source}`);
        }
      }
      await reindex();
      break;
    }

    case 'remove': {
      if (!rest.length) throw new Error('usage: bun run remove <skill|repo>...');
      const names = resolveNames(rest, await readLock());
      console.log(`removing ${names.length}: ${names.join(', ')}`);
      run(['remove', ...names, '-a', AGENT, '-y']);
      await reindex();
      break;
    }

    case 'sync':
      await sync();
      await reindex();
      break;

    case 'check':
      await reindex(true);
      break;

    case 'test':
      selftest();
      break;

    default:
      await reindex();
  }
}

// A usage mistake should read as one line, not a Bun stack trace into index.ts.
try {
  await main();
} catch (e) {
  console.error(`✗ ${(e as Error).message}`);
  process.exit(1);
}
