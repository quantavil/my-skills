import { expect, test } from 'bun:test';
import path from 'node:path';
import { repoAt } from '../lib/repo';
import { readManifest } from '../lib/manifest';
import { readLock } from '../lib/upstream';

// Library policy, rather than a restriction on the generic manager:
// each upstream collection has one discovery entry; local skills stay independent.
test('upstream collections are not scattered between standalone entries and bundles', async () => {
  const repo = repoAt(path.resolve(import.meta.dirname, '..'));
  const manifest = (await readManifest(repo))!;
  const lock = await readLock(repo);
  const groups = new Map<string, string[]>();
  for (const [name, entry] of Object.entries(lock)) {
    if (entry.sourceType === 'local' || !manifest.skills[name]) continue;
    const members = groups.get(entry.source) ?? [];
    members.push(name);
    groups.set(entry.source, members);
  }
  for (const [source, names] of groups) {
    if (names.length < 2) continue;
    const owners = names.map(name => Object.entries(manifest.superskills)
      .filter(([, def]) => def.members.includes(name)).map(([bundle]) => bundle));
    expect(owners.every(owner => owner.length === 1), `${source}: every member needs exactly one bundle`).toBe(true);
    expect(new Set(owners.flat()).size, `${source}: collection must have one router`).toBe(1);
  }
});

test('bundle membership is unique across the library', async () => {
  const repo = repoAt(path.resolve(import.meta.dirname, '..'));
  const manifest = (await readManifest(repo))!;
  const members = Object.values(manifest.superskills).flatMap(def => def.members);
  expect(new Set(members).size).toBe(members.length);
});
