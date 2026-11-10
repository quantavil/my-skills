import { afterEach, beforeEach, expect, test } from 'bun:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { build, bundleSkills, desiredLinks, findSkillDirs } from '../lib/bundles';
import { FINDER, readConfig, repoAt, validateConfig, type Repo } from '../lib/config';
import { deploy } from '../lib/deploy';
import { runBuild, runCheck, runSync } from '../index';

let root: string, home: string, up: string, repo: Repo;

const skill = (dir: string, name: string, description = `${name} skill`, extra: Record<string, string> = {}) => {
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'SKILL.md'), `---\nname: ${name}\ndescription: ${JSON.stringify(description)}\n---\n\n# ${name}\n`);
  for (const [rel, body] of Object.entries(extra)) {
    fs.mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true });
    fs.writeFileSync(path.join(dir, rel), body);
  }
};
const git = (dir: string, ...args: string[]) => Bun.spawnSync(['git', '-C', dir, ...args], { stderr: 'pipe' });
const commit = (dir: string) => {
  git(dir, 'init', '-q');
  git(dir, 'add', '-A');
  git(dir, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'x');
};
const writeConfig = (bundles: object, targets = ['claude']) =>
  fs.writeFileSync(repo.configPath, JSON.stringify({ targets, bundles }, null, 2));

beforeEach(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), 'ms-repo-'));
  home = fs.mkdtempSync(path.join(os.tmpdir(), 'ms-home-'));
  up = fs.mkdtempSync(path.join(os.tmpdir(), 'ms-up-'));
  repo = repoAt(root);
  fs.writeFileSync(repo.readmePath, '# t\n\n<!-- bundles:start -->\n<!-- bundles:end -->\n');
  // An upstream repo with two skills, one mirrored under plugins/ the way some repos ship them.
  skill(path.join(up, 'kit/skills/alpha'), 'alpha', 'Alpha things', { 'scripts/run.sh': 'echo hi' });
  skill(path.join(up, 'kit/skills/beta'), 'beta');
  skill(path.join(up, 'kit/plugins/x/skills/alpha'), 'alpha', 'stale copy');
  commit(path.join(up, 'kit'));
  skill(path.join(up, 'solo'), 'solo');
  commit(path.join(up, 'solo'));
  skill(path.join(repo.skillsDir, 'mine'), 'mine');
  writeConfig({
    kit: { repo: path.join(up, 'kit'), tier: 'core', summary: 'kit work' },
    solo: { repo: path.join(up, 'solo'), tier: 'gateway', summary: 'solo work' },
    mine: { tier: 'gateway', summary: 'my work' },
  });
});
afterEach(() => [root, home, up].forEach((d) => fs.rmSync(d, { recursive: true, force: true })));

test('sync imports every skill of a repo once, shallowest copy winning; a root skill stays whole', async () => {
  await runSync(repo, []);
  expect(bundleSkills(path.join(repo.vendorDir, 'kit')).map((s) => s.description)).toEqual(['Alpha things', 'beta skill']);
  expect(bundleSkills(path.join(repo.vendorDir, 'solo')).map((s) => s.name)).toEqual(['solo']);
  expect(findSkillDirs(path.join(up, 'solo'))).toEqual([path.join(up, 'solo')]);
});

test('sync overwrites local edits and prunes vendor folders no bundle uses', async () => {
  await runSync(repo, []);
  fs.writeFileSync(path.join(repo.vendorDir, 'kit/beta/SKILL.md'), 'edited');
  fs.mkdirSync(path.join(repo.vendorDir, 'gone'));
  await runSync(repo, []);
  expect(fs.readFileSync(path.join(repo.vendorDir, 'kit/beta/SKILL.md'), 'utf8')).toContain('beta skill');
  expect(fs.existsSync(path.join(repo.vendorDir, 'gone'))).toBe(false);
});

test('multi-skill bundles get a router over GUIDE.md copies; find-skill lists the gateway tier', async () => {
  await runSync(repo, []);
  const router = fs.readFileSync(path.join(repo.buildDir, 'kit/SKILL.md'), 'utf8');
  expect(router).toContain('description: "Use for kit work.');
  expect(router).toContain('[alpha](alpha/GUIDE.md)');
  expect(fs.existsSync(path.join(repo.buildDir, 'kit/alpha/SKILL.md'))).toBe(false);
  expect(fs.existsSync(path.join(repo.buildDir, 'kit/alpha/scripts/run.sh'))).toBe(true);

  const finder = fs.readFileSync(path.join(repo.buildDir, FINDER, 'SKILL.md'), 'utf8');
  expect(finder).toContain('and for: solo work; my work.');
  expect(finder).toContain(path.join(repo.skillsDir, 'mine', 'SKILL.md'));
  expect(fs.existsSync(path.join(repo.buildDir, 'solo'))).toBe(false); // one skill: linked directly
});

test('deploy links core bundles and find-skill, replaces and removes only its own links', async () => {
  await runSync(repo, []);
  const dir = path.join(home, '.claude/skills');
  fs.mkdirSync(dir, { recursive: true });
  fs.symlinkSync(path.join(root, 'skills/old'), path.join(dir, 'old'));
  fs.symlinkSync(up, path.join(dir, 'foreign'));
  const config = readConfig(repo);
  deploy(repo, home, config.targets, desiredLinks(repo, config), false);
  expect(fs.readdirSync(dir).sort()).toEqual([FINDER, 'foreign', 'kit']);
  expect(fs.readlinkSync(path.join(dir, 'kit'))).toBe(path.join(repo.buildDir, 'kit'));

  fs.mkdirSync(path.join(dir, 'blocker'));
  expect(() => deploy(repo, home, config.targets, new Map([['blocker', up]]), false)).toThrow('conflicts');
});

test('check reports a stale build, a stale README and a missing sync', async () => {
  expect(runCheck(repo).some((p) => p.includes('run sync'))).toBe(true);
  await runSync(repo, []);
  expect(runCheck(repo)).toEqual([]);
  fs.writeFileSync(path.join(repo.buildDir, 'kit/SKILL.md'), 'edited');
  expect(runCheck(repo)).toContain('.build/ is stale (run ./run.sh)');
  runBuild(repo);
  fs.writeFileSync(repo.readmePath, '# t\n\n<!-- bundles:start -->\n<!-- bundles:end -->\n');
  expect(runCheck(repo)).toContain('README.md table is stale (run ./run.sh)');
});

test('a one-skill bundle must be named like its skill', async () => {
  writeConfig({ other: { repo: path.join(up, 'solo'), tier: 'core', summary: 's' } });
  await runSync(repo, ['other']).catch(() => {});
  expect(() => build(repo, readConfig(repo))).toThrow('rename the bundle');
});

test('config rejects unknown fields, bad tiers, missing summaries and the reserved name', () => {
  const one = (b: object) => () => validateConfig({ bundles: { a: { tier: 'core', summary: 's', ...b } } });
  expect(one({ extra: 1 })).toThrow('unknown field');
  expect(one({ tier: 'x' })).toThrow('tier must be');
  expect(one({ summary: ' ' })).toThrow('summary is required');
  expect(() => validateConfig({ bundles: { [FINDER]: { tier: 'core', summary: 's' } } })).toThrow('reserved');
});
