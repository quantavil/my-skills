import { afterEach, beforeEach, describe, expect, test } from 'bun:test';
import fs from 'node:fs';
import path from 'node:path';
import { deployGlobal, doctor, resolveState } from '../lib/deploy';
import { readLocal, readManifest, writeLocal, writeManifest, type Manifest } from '../lib/manifest';
import { reindex } from '../lib/reindex';
import { listSkills } from '../lib/skills';
import { addSkill, makeSandbox, writeJson } from './helpers';

const CLAUDE = '.claude/skills';
let sb: ReturnType<typeof makeSandbox>;

beforeEach(async () => {
  sb = makeSandbox();
  addSkill(sb.repo, 'a', 'skill a');
  addSkill(sb.repo, 'b', 'skill b');
  addSkill(sb.repo, 'c', 'skill c');
  await reindex(sb.repo);
});
afterEach(() => sb.cleanup());

async function deploy(dryRun = false) {
  const skills = listSkills(sb.repo);
  const manifest = (await readManifest(sb.repo))!;
  const states = resolveState(manifest, await readLocal(sb.repo), skills);
  return deployGlobal(sb.repo, skills, states, sb.home, dryRun, ['claude', 'opencode', 'gemini']);
}

const linkPath = (name: string, dir = CLAUDE) => path.join(sb.home, dir, name);
const isLink = (name: string, dir = CLAUDE) => {
  try {
    return fs.lstatSync(linkPath(name, dir)).isSymbolicLink();
  } catch {
    return false;
  }
};
const activeNames = () => (fs.existsSync(sb.repo.activeDir) ? fs.readdirSync(sb.repo.activeDir).sort() : []);

async function setManifest(edit: (m: Manifest) => void) {
  const m = (await readManifest(sb.repo))!;
  edit(m);
  await writeManifest(sb.repo, m);
}

describe('enable and disable', () => {
  test('a disabled skill is unlinked everywhere and removed from the active set', async () => {
    await deploy();
    expect(isLink('a')).toBe(true);
    await writeLocal(sb.repo, { disabled: ['a'] });
    await deploy();
    expect(isLink('a')).toBe(false);
    expect(isLink('b')).toBe(true);
    expect(activeNames()).toEqual(['b', 'c']);
  });

  test('dry run changes nothing', async () => {
    const lines = await deploy(true);
    expect(lines.join('\n')).toContain('[dry run]');
    expect(isLink('a')).toBe(false);
  });
});

describe('superskills', () => {
  test('bundle members stay hidden when the bundle is disabled', async () => {
    await setManifest((m) => {
      m.superskills.bundle = { members: ['a', 'b'], description: 'squash of a and b' };
    });
    await reindex(sb.repo);
    await deploy();
    expect(isLink('bundle')).toBe(true);
    expect(isLink('a')).toBe(false);
    expect(isLink('b')).toBe(false);
    expect(isLink('c')).toBe(true);

    await writeLocal(sb.repo, { disabled: ['bundle'] });
    await deploy();
    expect(isLink('bundle')).toBe(false);
    expect(isLink('a')).toBe(false);
    expect(isLink('b')).toBe(false);
  });

});

describe('conflicts and foreign links', () => {
  test('a real folder in the way is reported and left untouched', async () => {
    fs.mkdirSync(linkPath('a'), { recursive: true });
    fs.writeFileSync(path.join(linkPath('a'), 'mine.md'), 'keep me');
    await expect(deploy()).rejects.toThrow('a: a real file or folder is in the way');
    expect(fs.readFileSync(path.join(linkPath('a'), 'mine.md'), 'utf8')).toBe('keep me');
  });

  test('a foreign link with the same name is not overwritten', async () => {
    const elsewhere = fs.mkdtempSync(path.join(sb.home, 'elsewhere-'));
    fs.mkdirSync(path.join(sb.home, CLAUDE), { recursive: true });
    fs.symlinkSync(elsewhere, linkPath('b'), 'dir');
    await expect(deploy()).rejects.toThrow('not ours, left alone');
    expect(fs.readlinkSync(linkPath('b'))).toBe(elsewhere);
  });

  test('foreign dangling links are preserved even when names match', async () => {
    fs.mkdirSync(path.join(sb.home, CLAUDE), { recursive: true });
    fs.symlinkSync('/nonexistent-old-repo/skills/a', linkPath('a'), 'dir');
    fs.symlinkSync('/nonexistent-old-repo/skills/gone', linkPath('gone'), 'dir');
    await expect(deploy()).rejects.toThrow('not ours');
    expect(fs.readlinkSync(linkPath('a'))).toBe('/nonexistent-old-repo/skills/a');
    expect(isLink('gone')).toBe(true);
  });
});

describe('agent configs', () => {
  test('Gemini and OpenCode point at the active set, not the repo skills folder', async () => {
    writeJson(path.join(sb.home, '.gemini/config/skills.json'), { entries: [{ path: sb.repo.skillsDir }, { path: '/other' }] });
    writeJson(path.join(sb.home, '.config/opencode/opencode.json'), { skills: [sb.repo.skillsDir] });
    await deploy();
    const gemini = JSON.parse(fs.readFileSync(path.join(sb.home, '.gemini/config/skills.json'), 'utf8'));
    expect(gemini.entries.map((e: { path: string }) => e.path)).toEqual(['/other', sb.repo.activeDir]);
    const opencode = JSON.parse(fs.readFileSync(path.join(sb.home, '.config/opencode/opencode.json'), 'utf8'));
    expect(opencode.skills.paths).toEqual([sb.repo.activeDir]);
  });

  test('malformed agent config is an error, never overwritten', async () => {
    fs.mkdirSync(path.join(sb.home, '.config/opencode'), { recursive: true });
    fs.writeFileSync(path.join(sb.home, '.config/opencode/opencode.json'), '{ not json');
    await expect(deploy()).rejects.toThrow();
    expect(fs.readFileSync(path.join(sb.home, '.config/opencode/opencode.json'), 'utf8')).toBe('{ not json');
  });
});

describe('doctor', () => {
  test('is clean after a deploy, and reports the gap when state changes without one', async () => {
    await deploy();
    const skills = listSkills(sb.repo);
    const manifest = (await readManifest(sb.repo))!;
    expect(doctor(sb.repo, skills, resolveState(manifest, await readLocal(sb.repo), skills), sb.home, ['claude', 'opencode', 'gemini'])).toEqual([]);

    await writeLocal(sb.repo, { disabled: ['a'] });
    const issues = doctor(sb.repo, skills, resolveState(manifest, await readLocal(sb.repo), skills), sb.home, ['claude', 'opencode', 'gemini']);
    expect(issues.some((i) => i.startsWith('a is still linked'))).toBe(true);
  });
});

describe('local state', () => {
  test('skills.local.json round-trips with sorted, unique entries', async () => {
    await writeLocal(sb.repo, { disabled: ['b', 'a', 'a'] });
    expect((await readLocal(sb.repo)).disabled).toEqual(['a', 'b']);
  });
});
