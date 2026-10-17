import { afterEach, beforeEach, describe, expect, test } from 'bun:test';
import fs from 'node:fs';
import path from 'node:path';
import { readLock } from '../lib/upstream';
import { readManifest, writeManifest } from '../lib/manifest';
import { reindex, readmeMatches } from '../lib/reindex';
import { listSkills } from '../lib/skills';
import { verify } from '../lib/verify';
import { addSkill, makeSandbox, skillText } from './helpers';

let sb: ReturnType<typeof makeSandbox>;

beforeEach(async () => {
  sb = makeSandbox();
  addSkill(sb.repo, 'a', 'skill a');
  addSkill(sb.repo, 'b', 'skill b');
  await reindex(sb.repo);
});
afterEach(() => sb.cleanup());

async function problems() {
  return verify(sb.repo, listSkills(sb.repo), await readLock(sb.repo), await readManifest(sb.repo));
}

describe('reindex', () => {
  test('seeds skills.json, pins locals, writes the README, and is idempotent', async () => {
    const m = (await readManifest(sb.repo))!;
    expect(m.skills.a).toMatchObject({ type: 'local' });
    expect(await readmeMatches(sb.repo, listSkills(sb.repo), await readLock(sb.repo), m)).toBe(true);
    expect(await reindex(sb.repo)).toEqual([]);
  });

  test('a skill that vanished from disk is pruned from skills.json', async () => {
    fs.rmSync(path.join(sb.repo.skillsDir, 'b'), { recursive: true });
    await reindex(sb.repo);
    expect((await readManifest(sb.repo))!.skills.b).toBeUndefined();
  });
});

describe('verify', () => {
  test('a clean repo has no problems', async () => {
    expect(await problems()).toEqual([]);
  });

  test('editing a local skill is flagged until the next index', async () => {
    fs.appendFileSync(path.join(sb.repo.skillsDir, 'a', 'SKILL.md'), '\nmore\n');
    expect((await problems()).some((p) => p.startsWith('a: local skill changed'))).toBe(true);
    await reindex(sb.repo);
    expect(await problems()).toEqual([]);
  });

  test('editing a vendored skill is an error that index does not silently accept', async () => {
    const m = (await readManifest(sb.repo))!;
    m.skills.a!.type = 'upstream';
    await writeManifest(sb.repo, m);
    fs.appendFileSync(path.join(sb.repo.skillsDir, 'a', 'SKILL.md'), '\nlocal fix\n');
    await reindex(sb.repo);
    expect((await problems()).some((p) => p.includes('vendored skill changed on disk'))).toBe(true);
    expect((await readManifest(sb.repo))!.skills.a!.type).toBe('upstream');
  });


  test('a superskill goes stale when a member changes', async () => {
    const m = (await readManifest(sb.repo))!;
    m.superskills.bundle = { members: ['a', 'b'], description: 'squash' };
    await writeManifest(sb.repo, m);
    await reindex(sb.repo);
    expect(await problems()).toEqual([]);

    fs.writeFileSync(path.join(sb.repo.sourcesDir, 'b', 'GUIDE.md'), skillText('b', 'skill b', '# changed\n'));
    expect((await problems()).some((p) => p.startsWith('bundle: superskill is stale'))).toBe(true);
  });

  test('a hand-edited superskill is reported', async () => {
    const m = (await readManifest(sb.repo))!;
    m.superskills.bundle = { members: ['a'], description: 'squash' };
    await writeManifest(sb.repo, m);
    await reindex(sb.repo);
    fs.appendFileSync(path.join(sb.repo.superDir, 'bundle', 'SKILL.md'), '\nhand edit\n');
    expect((await problems()).some((p) => p.startsWith('bundle: superskill is stale'))).toBe(true);
  });
});
