import { afterEach, beforeEach, expect, test } from 'bun:test';
import fs from 'node:fs';
import path from 'node:path';
import { buildSuperFiles, resolveMembers, writeSuper } from '../lib/superskill';
import { deployGlobal, doctor, resolveState } from '../lib/deploy';
import { readManifest, writeManifest } from '../lib/manifest';
import { listSkills } from '../lib/skills';
import { reindex } from '../lib/reindex';
import { readLock, runSkills, writeLock } from '../lib/upstream';
import { sourceHash } from '../lib/hash';
import { addSkill, makeSandbox, skillText, writeJson } from './helpers';

let sb: ReturnType<typeof makeSandbox>;
beforeEach(() => { sb = makeSandbox(); });
afterEach(() => sb.cleanup());

async function state() {
  const skills = listSkills(sb.repo);
  return { skills, states: resolveState((await readManifest(sb.repo))!, { disabled: [] }, skills) };
}

function installManager() {
  fs.copyFileSync(path.resolve('index.ts'), path.join(sb.root, 'index.ts'));
  fs.cpSync(path.resolve('lib'), path.join(sb.root, 'lib'), { recursive: true });
}
function cli(...args: string[]) {
  return Bun.spawnSync([process.execPath, path.join(sb.root, 'index.ts'), ...args], {
    cwd: sb.root, env: { ...process.env, HOME: sb.home }, stdout: 'pipe', stderr: 'pipe',
  });
}

test('routers preserve member commands and executable permissions', () => {
  addSkill(sb.repo, 'alpha', 'Do alpha', { 'scripts/run.sh': '#!/bin/sh\necho ok\n' });
  fs.chmodSync(path.join(sb.repo.skillsDir, 'alpha/scripts/run.sh'), 0o755);
  fs.writeFileSync(path.join(sb.repo.skillsDir, 'alpha/SKILL.md'), skillText('alpha', 'Do alpha', 'SECRET MEMBER BODY\nRun `./scripts/run.sh` from the directory containing this SKILL.md.\n'));
  const def = { members: ['alpha'], description: 'Alpha tasks' };
  const files = buildSuperFiles('bundle', def, resolveMembers(listSkills(sb.repo), def.members, 'bundle'));
  const router = files.find(f => f.rel === 'SKILL.md')!.buf.toString();
  expect(router).not.toContain('SECRET MEMBER BODY');
  expect(router).toContain('working directory');
  expect(files.filter(f => path.basename(f.rel) === 'SKILL.md')).toHaveLength(1);
  expect(files.find(f => f.rel === 'alpha/GUIDE.md')!.buf.toString()).toContain('`./scripts/run.sh`');
  writeSuper(sb.repo, 'bundle', files);
  const command = Bun.spawnSync(['./scripts/run.sh'], { cwd: path.join(sb.repo.superDir, 'bundle/alpha') });
  expect(command.exitCode).toBe(0);
  expect(command.stdout.toString().trim()).toBe('ok');
});

test('doctor detects a config pointing to the full library after links are deployed', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); await reindex(sb.repo);
  const { skills, states } = await state();
  await deployGlobal(sb.repo, skills, states, sb.home, false, ['claude', 'opencode', 'gemini']);
  writeJson(path.join(sb.home, '.config/opencode/opencode.json'), { skills: { paths: [sb.repo.skillsDir], urls: ['https://example.com'] } });
  expect(doctor(sb.repo, skills, states, sb.home, ['claude', 'opencode', 'gemini']).some(p => p.includes('OpenCode'))).toBe(true);
});

test('deployment conflicts fail before changing other agent directories', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); await reindex(sb.repo);
  const { skills, states } = await state();
  fs.mkdirSync(path.join(sb.home, '.claude/skills/alpha'), { recursive: true });
  await expect(deployGlobal(sb.repo, skills, states, sb.home, false, ['claude', 'opencode', 'gemini'])).rejects.toThrow('conflict');
  expect(fs.existsSync(sb.repo.activeDir)).toBe(false);
});

test('inspection commands never generate missing bundles', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); await reindex(sb.repo);
  const m = (await readManifest(sb.repo))!;
  m.superskills.bundle = { members: ['alpha'], description: 'Alpha tasks' };
  await writeManifest(sb.repo, m); await reindex(sb.repo);
  fs.rmSync(sb.repo.superDir, { recursive: true });
  installManager();
  for (const command of [['status'], ['doctor'], ['check'], ['deploy', '--dry-run']]) {
    cli(...command);
    expect(fs.existsSync(sb.repo.superDir)).toBe(false);
    expect(fs.existsSync(sb.repo.activeDir)).toBe(false);
  }
});

test('accept makes an upstream customization local so sync cannot overwrite it', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); await reindex(sb.repo);
  const m = (await readManifest(sb.repo))!; m.skills.alpha!.type = 'upstream'; await writeManifest(sb.repo, m);
  fs.appendFileSync(path.join(sb.repo.skillsDir, 'alpha/SKILL.md'), '\nMy customization\n');
  installManager();
  expect(cli('set', 'alpha', '--accept').exitCode).toBe(0);
  expect((await readManifest(sb.repo))!.skills.alpha!.type).toBe('local');
  expect(fs.existsSync(path.join(sb.home, '.codex'))).toBe(false);
});

test('upstream staging preserves project .agents files', async () => {
  fs.mkdirSync(path.join(sb.root, '.agents'), { recursive: true });
  fs.writeFileSync(path.join(sb.root, '.agents/mine.md'), 'keep');
  const bin = path.join(sb.root, 'node_modules/skills/bin'); fs.mkdirSync(bin, { recursive: true });
  fs.writeFileSync(path.join(bin, 'cli.mjs'), `import fs from 'node:fs'; fs.mkdirSync('.agents/skills/alpha', {recursive:true}); fs.writeFileSync('.agents/skills/alpha/SKILL.md', ${JSON.stringify(skillText('alpha', 'Alpha'))}); fs.writeFileSync('skills-lock.json', JSON.stringify({version:1,skills:{alpha:{source:'o/r'}}}));`);
  await runSkills(sb.repo, ['add', 'o/r']);
  expect(fs.readFileSync(path.join(sb.root, '.agents/mine.md'), 'utf8')).toBe('keep');
  expect(fs.existsSync(path.join(sb.repo.skillsDir, 'alpha/SKILL.md'))).toBe(true);
});

test('only selected targets are deployed and unrelated configs stay untouched', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); await reindex(sb.repo);
  const { skills, states } = await state();
  await deployGlobal(sb.repo, skills, states, sb.home, false, ['claude']);
  expect(fs.existsSync(path.join(sb.home, '.claude/skills/alpha/SKILL.md'))).toBe(true);
  expect(fs.existsSync(path.join(sb.home, '.codex'))).toBe(false);
  expect(fs.existsSync(path.join(sb.home, '.gemini'))).toBe(false);
  expect(fs.existsSync(path.join(sb.home, '.config/opencode'))).toBe(false);
  expect(doctor(sb.repo, skills, states, sb.home, ['claude'])).toEqual([]);
});

test('rebuild never deploys and targets are saved separately', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); installManager();
  expect(cli().exitCode).toBe(0);
  expect(fs.existsSync(sb.repo.activeDir)).toBe(false);
  expect(cli('targets', 'claude').exitCode).toBe(0);
  expect(fs.existsSync(path.join(sb.home, '.claude'))).toBe(false);
  expect(cli('deploy', '--dry-run').exitCode).toBe(0);
  expect(fs.existsSync(sb.repo.activeDir)).toBe(false);
  expect(cli('deploy').exitCode).toBe(0);
  expect(fs.existsSync(path.join(sb.home, '.claude/skills/alpha/SKILL.md'))).toBe(true);
  expect(fs.existsSync(path.join(sb.home, '.codex'))).toBe(false);
  expect(cli('doctor').exitCode).toBe(0);
});

test('unknown flags fail instead of silently changing behavior', () => {
  installManager();
  expect(cli('sync', '--froce').exitCode).toBe(1);
  expect(cli('set', 'alpha', '--type', '--accept').exitCode).toBe(1);
});

test('failed upstream command preserves both vendored skills and project agent files', async () => {
  addSkill(sb.repo, 'alpha', 'Original'); await reindex(sb.repo);
  const original = fs.readFileSync(path.join(sb.repo.skillsDir, 'alpha/SKILL.md'), 'utf8');
  const lock = fs.readFileSync(sb.repo.lockPath, 'utf8');
  fs.mkdirSync(path.join(sb.root, '.agents'), { recursive: true }); fs.writeFileSync(path.join(sb.root, '.agents/mine'), 'keep');
  const bin = path.join(sb.root, 'node_modules/skills/bin'); fs.mkdirSync(bin, { recursive: true });
  fs.writeFileSync(path.join(bin, 'cli.mjs'), 'process.exit(1);');
  await expect(runSkills(sb.repo, ['add', 'o/r'])).rejects.toThrow('failed');
  expect(fs.readFileSync(path.join(sb.repo.skillsDir, 'alpha/SKILL.md'), 'utf8')).toBe(original);
  expect(fs.readFileSync(sb.repo.lockPath, 'utf8')).toBe(lock);
  expect(fs.readFileSync(path.join(sb.root, '.agents/mine'), 'utf8')).toBe('keep');
});

test('structured OpenCode settings preserve URL sources during registration', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); await reindex(sb.repo);
  writeJson(path.join(sb.home, '.config/opencode/opencode.json'), { skills: { paths: [sb.repo.skillsDir, '/other'], urls: ['https://example.com'] }, theme: 'custom' });
  const { skills, states } = await state();
  await deployGlobal(sb.repo, skills, states, sb.home, false, ['opencode']);
  const config = JSON.parse(fs.readFileSync(path.join(sb.home, '.config/opencode/opencode.json'), 'utf8'));
  expect(config.skills).toEqual({ paths: ['/other', sb.repo.activeDir], urls: ['https://example.com'] });
  expect(config.theme).toBe('custom');
});

test('adding an upstream skill cannot overwrite a local customization', async () => {
  addSkill(sb.repo, 'alpha', 'My local skill'); await reindex(sb.repo);
  const before = fs.readFileSync(path.join(sb.repo.skillsDir, 'alpha/SKILL.md'), 'utf8');
  const bin = path.join(sb.root, 'node_modules/skills/bin'); fs.mkdirSync(bin, { recursive: true });
  fs.writeFileSync(path.join(bin, 'cli.mjs'), `import fs from 'node:fs'; fs.mkdirSync('.agents/skills/alpha', {recursive:true}); fs.writeFileSync('.agents/skills/alpha/SKILL.md', ${JSON.stringify(skillText('alpha', 'Upstream replacement'))}); fs.writeFileSync('skills-lock.json', JSON.stringify({version:1,skills:{alpha:{source:'o/r'}}}));`);
  await expect(runSkills(sb.repo, ['add', 'o/r'])).rejects.toThrow('local');
  expect(fs.readFileSync(path.join(sb.repo.skillsDir, 'alpha/SKILL.md'), 'utf8')).toBe(before);
});


test('the pinned upstream CLI can import a local fixture through isolated staging', async () => {
  const source = path.join(sb.root, 'source/alpha'); fs.mkdirSync(source, { recursive: true });
  fs.writeFileSync(path.join(source, 'SKILL.md'), skillText('alpha', 'Fixture skill'));
  fs.mkdirSync(path.join(sb.root, 'node_modules'), { recursive: true });
  fs.symlinkSync(path.resolve('node_modules/skills'), path.join(sb.root, 'node_modules/skills'), 'dir');
  const telemetry = process.env.DISABLE_TELEMETRY;
  process.env.DISABLE_TELEMETRY = '1';
  try {
    await runSkills(sb.repo, ['add', path.dirname(source), '-s', 'alpha', '-a', 'universal', '--copy', '-y']);
    expect(fs.readFileSync(path.join(sb.repo.skillsDir, 'alpha/SKILL.md'), 'utf8')).toContain('Fixture skill');
    const lock = JSON.parse(fs.readFileSync(sb.repo.lockPath, 'utf8'));
    expect(lock.skills.alpha).toBeDefined();
  } finally {
    if (telemetry === undefined) delete process.env.DISABLE_TELEMETRY;
    else process.env.DISABLE_TELEMETRY = telemetry;
  }
});

test('bundled members are physically removed from skills discovery and retain their source hash', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); addSkill(sb.repo, 'beta', 'Beta'); await reindex(sb.repo);
  const m = (await readManifest(sb.repo))!;
  const originalHash = m.skills.alpha!.contentHash;
  const original = fs.readFileSync(path.join(sb.repo.skillsDir, 'alpha/SKILL.md'), 'utf8');
  m.superskills.bundle = { members: ['alpha'], description: 'Alpha tasks' };
  await writeManifest(sb.repo, m); await reindex(sb.repo);
  expect(fs.existsSync(path.join(sb.repo.skillsDir, 'alpha'))).toBe(false);
  expect(fs.readFileSync(path.join(sb.root, 'sources/alpha/GUIDE.md'), 'utf8')).toBe(original);
  expect(fs.existsSync(path.join(sb.root, 'sources/alpha/SKILL.md'))).toBe(false);
  expect((await readManifest(sb.repo))!.skills.alpha!.contentHash).toBe(originalHash);
  expect(listSkills(sb.repo).map(s => s.name).sort()).toEqual(['alpha', 'beta', 'bundle']);
  expect(await reindex(sb.repo)).toEqual([]);
});

test('removing a bundle restores its members to standalone source folders', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); await reindex(sb.repo);
  const m = (await readManifest(sb.repo))!;
  m.superskills.bundle = { members: ['alpha'], description: 'Alpha tasks' };
  await writeManifest(sb.repo, m); await reindex(sb.repo); installManager();
  expect(fs.existsSync(path.join(sb.repo.skillsDir, 'alpha'))).toBe(false);
  expect(cli('remove', 'bundle').exitCode).toBe(0);
  expect(fs.existsSync(path.join(sb.repo.skillsDir, 'alpha/SKILL.md'))).toBe(true);
  expect(fs.existsSync(path.join(sb.root, 'sources/alpha'))).toBe(false);
});

test('upstream updates archived members in place without leaking them back into skills', async () => {
  addSkill(sb.repo, 'alpha', 'Original'); await reindex(sb.repo);
  const m = (await readManifest(sb.repo))!;
  m.skills.alpha!.type = 'upstream';
  m.superskills.bundle = { members: ['alpha'], description: 'Alpha tasks' };
  await writeManifest(sb.repo, m); await reindex(sb.repo);
  const bin = path.join(sb.root, 'node_modules/skills/bin'); fs.mkdirSync(bin, { recursive: true });
  fs.writeFileSync(path.join(bin, 'cli.mjs'), `import fs from 'node:fs'; const lock=JSON.parse(fs.readFileSync('skills-lock.json','utf8')); fs.mkdirSync('.agents/skills/alpha', {recursive:true}); fs.writeFileSync('.agents/skills/alpha/SKILL.md', ${JSON.stringify(skillText('alpha', 'Updated upstream'))}); fs.writeFileSync('skills-lock.json', JSON.stringify(lock));`);
  await runSkills(sb.repo, ['add', 'o/r']);
  expect(fs.existsSync(path.join(sb.repo.skillsDir, 'alpha'))).toBe(false);
  expect(fs.readFileSync(path.join(sb.repo.sourcesDir, 'alpha/GUIDE.md'), 'utf8')).toContain('Updated upstream');
  expect(fs.existsSync(path.join(sb.repo.sourcesDir, 'alpha/SKILL.md'))).toBe(false);
});

test('accept resolves an archived guide rather than recreating a standalone skill', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); await reindex(sb.repo);
  const m = (await readManifest(sb.repo))!; m.skills.alpha!.type = 'upstream';
  m.superskills.bundle = { members: ['alpha'], description: 'Alpha tasks' };
  await writeManifest(sb.repo, m); await reindex(sb.repo);
  fs.appendFileSync(path.join(sb.repo.sourcesDir, 'alpha/GUIDE.md'), '\nMy edits\n');
  installManager();
  expect(cli('set', 'alpha', '--accept').exitCode).toBe(0);
  expect((await readManifest(sb.repo))!.skills.alpha!.type).toBe('local');
  expect(fs.existsSync(path.join(sb.repo.skillsDir, 'alpha'))).toBe(false);
});

function fakeUpstream(script: string) {
  const bin = path.join(sb.root, 'node_modules/skills/bin');
  fs.mkdirSync(bin, { recursive: true });
  fs.writeFileSync(path.join(bin, 'cli.mjs'), script);
}

test('import refuses a bundle name collision even with force', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); await reindex(sb.repo);
  const m = (await readManifest(sb.repo))!;
  m.superskills.bundle = { members: ['alpha'], description: 'Alpha tasks' };
  await writeManifest(sb.repo, m); await reindex(sb.repo);
  fakeUpstream(`import fs from 'node:fs'; fs.mkdirSync('.agents/skills/bundle', {recursive:true}); fs.writeFileSync('.agents/skills/bundle/SKILL.md', ${JSON.stringify(skillText('bundle', 'Collision'))}); fs.writeFileSync('skills-lock.json', JSON.stringify({version:1,skills:{bundle:{source:'o/r'}}}));`);
  await expect(runSkills(sb.repo, ['add', 'o/r'], true)).rejects.toThrow('bundle');
  expect(fs.existsSync(path.join(sb.repo.skillsDir, 'bundle'))).toBe(false);
});

test('re-import records requested ownership even when the upstream lock is unchanged', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); await reindex(sb.repo); installManager();
  fakeUpstream(`import fs from 'node:fs'; fs.mkdirSync('.agents/skills/alpha', {recursive:true}); fs.writeFileSync('.agents/skills/alpha/SKILL.md', ${JSON.stringify(skillText('alpha', 'Alpha'))});`);
  expect(cli('add', 'o/r', '--type', 'upstream', '--force').exitCode).toBe(0);
  expect((await readManifest(sb.repo))!.skills.alpha!.type).toBe('upstream');
  });

test('a later sync failure preserves accepted hashes and rebuilt bundles for successful repos', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); addSkill(sb.repo, 'beta', 'Beta'); await reindex(sb.repo);
  const m = (await readManifest(sb.repo))!;
  m.skills.alpha!.type = 'upstream'; m.skills.beta!.type = 'upstream';
  m.superskills.bundle = { members: ['alpha'], description: 'Alpha tasks' };
  await writeManifest(sb.repo, m); await reindex(sb.repo);
  const lock = await readLock(sb.repo);
  lock.alpha = { source: 'o/first' }; lock.beta = { source: 'o/second' }; await writeLock(sb.repo, lock);
  installManager();
  fakeUpstream(`import fs from 'node:fs'; if(process.argv.includes('o/second')) process.exit(1); fs.mkdirSync('.agents/skills/alpha', {recursive:true}); fs.writeFileSync('.agents/skills/alpha/SKILL.md', ${JSON.stringify(skillText('alpha', 'Updated alpha'))});`);
  const first = cli('sync');
  expect(first.exitCode).toBe(1);
  expect((await readManifest(sb.repo))!.skills.alpha!.contentHash).toBe(sourceHash(path.join(sb.repo.sourcesDir, 'alpha')));
  expect(fs.readFileSync(path.join(sb.repo.superDir, 'bundle/SKILL.md'), 'utf8')).toContain('Updated alpha');
  const retry = cli('sync');
  expect(retry.stderr.toString()).not.toContain('edited locally');
});

test('force sync handles edits in more than one upstream repo', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); addSkill(sb.repo, 'beta', 'Beta'); await reindex(sb.repo);
  const m = (await readManifest(sb.repo))!;
  m.skills.alpha!.type = 'upstream'; m.skills.beta!.type = 'upstream'; await writeManifest(sb.repo, m);
  const lock = await readLock(sb.repo);
  lock.alpha = { source: 'o/first' }; lock.beta = { source: 'o/second' }; await writeLock(sb.repo, lock);
  for (const name of ['alpha', 'beta']) fs.appendFileSync(path.join(sb.repo.skillsDir, name, 'SKILL.md'), '\nLocal edit\n');
  installManager();
  fakeUpstream(`import fs from 'node:fs'; const name=process.argv.includes('o/first')?'alpha':'beta'; fs.mkdirSync('.agents/skills/'+name, {recursive:true}); fs.writeFileSync('.agents/skills/'+name+'/SKILL.md', '---\\nname: '+name+'\\ndescription: Updated\\n---\\n');`);
  const result = cli('sync', '--force');
  expect(result.stderr.toString()).toBe('');
  expect(result.exitCode).toBe(0);
  expect(cli('check').exitCode).toBe(0);
});

test('creating a local skill cannot reuse a bundle name', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha'); await reindex(sb.repo);
  const m = (await readManifest(sb.repo))!;
  m.superskills.bundle = { members: ['alpha'], description: 'Alpha tasks' };
  await writeManifest(sb.repo, m); await reindex(sb.repo); installManager();
  expect(cli('add', '--type', 'local', '--name', 'bundle', '--description', 'Collision').exitCode).toBe(1);
  expect(fs.existsSync(path.join(sb.repo.skillsDir, 'bundle'))).toBe(false);
});

test('malformed lock structures fail before rebuilding can replace them', async () => {
  addSkill(sb.repo, 'alpha', 'Alpha');
  for (const value of [{ version: 1, skills: [] }, { version: 1, skills: { alpha: {} } }, {}]) {
    writeJson(sb.repo.lockPath, value);
    const before = fs.readFileSync(sb.repo.lockPath, 'utf8');
    await expect(reindex(sb.repo)).rejects.toThrow('skills-lock.json');
    expect(fs.readFileSync(sb.repo.lockPath, 'utf8')).toBe(before);
  }
});

test('partial upstream selection fails without installing any of the requested skills', async () => {
  fakeUpstream(`import fs from 'node:fs'; fs.mkdirSync('.agents/skills/alpha', {recursive:true}); fs.writeFileSync('.agents/skills/alpha/SKILL.md', ${JSON.stringify(skillText('alpha', 'Alpha'))}); fs.writeFileSync('skills-lock.json', JSON.stringify({version:1,skills:{alpha:{source:'o/r'}}}));`);
  await expect(runSkills(sb.repo, ['add', 'o/r', '-s', 'alpha', '-s', 'beta'])).rejects.toThrow('beta');
  expect(fs.existsSync(path.join(sb.repo.skillsDir, 'alpha'))).toBe(false);
});

test('real upstream CLI supports add, bundled sync, deploy, visibility changes, and removal', async () => {
  const source = path.join(sb.root, 'upstream/alpha'); fs.mkdirSync(source, { recursive: true });
  fs.writeFileSync(path.join(source, 'SKILL.md'), skillText('alpha', 'Original fixture'));
  fs.mkdirSync(path.join(sb.root, 'node_modules'), { recursive: true });
  fs.symlinkSync(path.resolve('node_modules/skills'), path.join(sb.root, 'node_modules/skills'), 'dir');
  installManager();
  const run = (...args: string[]) => {
    const result = cli(...args);
    if (result.exitCode !== 0) throw new Error(result.stdout.toString() + result.stderr.toString());
    return result;
  };
  run('add', path.dirname(source), '--type', 'upstream');
  run('superskill', 'bundle', '--members', 'alpha', '--description', 'Fixture tasks');
  run('targets', 'codex', 'claude', 'gemini', 'opencode');
  run('deploy'); run('doctor');
  expect(fs.existsSync(path.join(sb.home, '.codex/skills/alpha'))).toBe(false);
  fs.writeFileSync(path.join(source, 'SKILL.md'), skillText('alpha', 'Updated fixture'));
  run('sync'); run('deploy'); run('check'); run('doctor');
  expect(fs.readFileSync(path.join(sb.home, '.codex/skills/bundle/alpha/GUIDE.md'), 'utf8')).toContain('# Body');
  expect(fs.readFileSync(path.join(sb.home, '.codex/skills/bundle/SKILL.md'), 'utf8')).toContain('Updated fixture');
  expect(fs.existsSync(path.join(sb.repo.skillsDir, 'alpha'))).toBe(false);
  expect(cli('disable', 'alpha').exitCode).toBe(1);
  expect(cli('enable', 'alpha').exitCode).toBe(1);
  run('disable', 'bundle'); run('deploy'); run('doctor');
  expect(fs.existsSync(path.join(sb.home, '.codex/skills/bundle'))).toBe(false);
  expect(fs.existsSync(path.join(sb.home, '.codex/skills/alpha'))).toBe(false);
  run('enable', 'bundle'); run('deploy'); run('doctor');
  expect(fs.existsSync(path.join(sb.home, '.codex/skills/alpha'))).toBe(false);
  run('remove', 'bundle', 'alpha'); run('deploy'); run('doctor');
  expect(fs.existsSync(path.join(sb.home, '.codex/skills/bundle'))).toBe(false);
}, 20000);

test('local creation takes explicit arguments and missing input leaves the library untouched', () => {
  installManager();
  expect(cli('add').exitCode).toBe(1);
  expect(cli('add', '--type', 'local', '--name', 'mine').exitCode).toBe(1);
  expect(fs.existsSync(path.join(sb.repo.skillsDir, 'mine'))).toBe(false);
  expect(cli('superskill').exitCode).toBe(1);
  expect(cli('add', '--type', 'local', '--name', 'mine', '--description', 'Use for my tasks').exitCode).toBe(0);
  expect(fs.readFileSync(path.join(sb.repo.skillsDir, 'mine/SKILL.md'), 'utf8')).toContain('Use for my tasks');
});
