import { expect, test } from 'bun:test';
import { parseArgs } from '../index';
import { validateManifest } from '../lib/manifest';
import { resolveState } from '../lib/deploy';
import type { SkillDir } from '../lib/skills';

test('removed command options fail explicitly', () => {
  for (const option of ['--category', '--requires', '--keep-members', '--index']) {
    expect(() => parseArgs([option, 'anything'])).toThrow('unknown option');
  }
});

test('manifest contains only ownership, integrity, and bundle definitions', () => {
  const raw = {
    version: 1 as const,
    skills: { alpha: { type: 'upstream' as const, contentHash: 'a'.repeat(64) } },
    superskills: { bundle: { members: ['alpha'], description: 'Alpha tasks' } },
  };
  expect(validateManifest(raw)).toEqual(raw);
  for (const key of ['category', 'requires']) {
    expect(() => validateManifest({ ...raw, skills: { alpha: { ...raw.skills.alpha, [key]: [] } } })).toThrow(key);
  }
  for (const key of ['hideMembers', 'mode']) {
    expect(() => validateManifest({ ...raw, superskills: { bundle: { ...raw.superskills.bundle, [key]: true } } })).toThrow(key);
  }
});

test('members never become standalone entries when their bundle is disabled', () => {
  const manifest = {
    version: 1 as const,
    skills: {},
    superskills: { bundle: { members: ['alpha'], description: 'Alpha tasks' } },
  };
  const skills: SkillDir[] = [
    { name: 'alpha', root: 'skills', abs: '/sources/alpha', description: 'Alpha' },
    { name: 'bundle', root: 'superskills', abs: '/superskills/bundle', description: 'Bundle' },
  ];
  const states = resolveState(manifest, { disabled: ['bundle'] }, skills);
  expect(states.get('bundle')?.state).toBe('off');
  expect(states.get('alpha')).toEqual({ state: 'hidden', by: 'bundle' });
});
