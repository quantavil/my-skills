import { afterEach, beforeEach, describe, expect, test } from 'bun:test';
import fs from 'node:fs';
import path from 'node:path';
import { folderHash, hashFiles } from '../lib/hash';
import { emptyLocal, validateManifest, emptyManifest, type Manifest } from '../lib/manifest';
import { addArgs, resolveNames, type Lock } from '../lib/upstream';
import { buildMarkdown, cell, render, sourceLink, UNSOURCED } from '../lib/readme';
import { parseFrontmatter, listSkills } from '../lib/skills';
import { generatedDescription, buildSuperFiles, resolveMembers } from '../lib/superskill';
import { parseArgs } from '../index';
import { addSkill, makeSandbox, skillText } from './helpers';

let sb: ReturnType<typeof makeSandbox>;
beforeEach(() => {
  sb = makeSandbox();
});
afterEach(() => sb.cleanup());

describe('parseArgs', () => {
  test('splits positionals, value flags, boolean flags and repeated -s', () => {
    const p = parseArgs(['owner/repo', '--type', 'local', '--force', '-s', 'one', '--skill', 'two', 'extra']);
    expect(p.pos).toEqual(['owner/repo', 'extra']);
    expect(p.opts.get('type')).toBe('local');
    expect(p.opts.get('force')).toBe(true);
    expect(p.skills).toEqual(['one', 'two']);
  });


  test('a value flag without a value is an error', () => {
    expect(() => parseArgs(['--type'])).toThrow('--type needs a value');
  });
});

describe('lock helpers', () => {
  test('addArgs defaults a bare repo to every skill and leaves an explicit -s alone', () => {
    expect(addArgs(['o/r']).join(' ')).toContain('o/r -s *');
    expect(addArgs(['o/r', '-s', 'one']).includes('*')).toBe(false);
  });

  test('resolveNames expands a repo, dedupes and rejects unknown names', () => {
    const lock: Lock = { a: { source: 'o/r' }, b: { source: 'o/r' }, c: { source: 'x/y' } };
    expect(resolveNames(['a'], lock)).toEqual(['a']);
    expect(resolveNames(['o/r'], lock)).toEqual(['a', 'b']);
    expect(resolveNames(['a', 'o/r'], lock)).toEqual(['a', 'b']);
    expect(() => resolveNames(['nope'], lock)).toThrow('not in this collection');
  });
});

describe('frontmatter and names', () => {
  test('parseFrontmatter rejects bad names, empty and oversized descriptions', () => {
    expect(parseFrontmatter('---\nname: demo\ndescription: does a | thing\n---\nbody').name).toBe('demo');
    expect(() => parseFrontmatter('---\nname: Invalid_Name\ndescription: test\n---')).toThrow('invalid name');
    expect(() => parseFrontmatter('---\nname: test\ndescription: ""\n---')).toThrow('cannot be empty');
    expect(() => parseFrontmatter(`---\nname: test\ndescription: ${'a'.repeat(1025)}\n---`)).toThrow('too long');
  });

  test('cell folds whitespace and escapes pipes', () => {
    expect(cell('does a | thing\n  over two lines')).toBe('does a \\| thing over two lines');
  });

});

describe('hashing', () => {
  test('folderHash matches the skills CLI algorithm (relative path, then bytes, sorted)', () => {
    const dir = path.join(sb.root, 'folder');
    fs.mkdirSync(path.join(dir, 'references'), { recursive: true });
    fs.writeFileSync(path.join(dir, 'SKILL.md'), 'a');
    fs.writeFileSync(path.join(dir, 'references/x.md'), 'b');
    // localeCompare sorts "references/x.md" before "SKILL.md", as the skills CLI does.
    const expected = new Bun.CryptoHasher('sha256').update('references/x.md').update('b').update('SKILL.md').update('a').digest('hex');
    expect(folderHash(dir)).toBe(expected);
  });

  test('folderHash ignores VCS and generated junk, so running a skill cannot change its hash', () => {
    const dir = path.join(sb.root, 'folder2');
    fs.mkdirSync(path.join(dir, '.git'), { recursive: true });
    fs.mkdirSync(path.join(dir, 'scripts/__pycache__'), { recursive: true });
    fs.writeFileSync(path.join(dir, 'SKILL.md'), 'a');
    const before = folderHash(dir);
    fs.writeFileSync(path.join(dir, '.git/HEAD'), 'ref');
    fs.writeFileSync(path.join(dir, 'scripts/__pycache__/x.cpython-313.pyc'), 'bytecode');
    fs.writeFileSync(path.join(dir, 'scripts/.DS_Store'), 'junk');
    expect(folderHash(dir)).toBe(before);
  });
});

describe('manifest validation', () => {
  test('accepts a well-formed manifest', () => {
    const hash = 'a'.repeat(64);
    const m = validateManifest({ version: 1, skills: { x: { type: 'local', contentHash: hash } }, superskills: {} });
    expect(m.skills.x?.type).toBe('local');
  });

  test('rejects unknown types and bad hashes', () => {
    const base = { version: 1, superskills: {} };
    expect(() => validateManifest({ ...base, skills: { x: { type: 'weird', contentHash: 'a'.repeat(64) } } })).toThrow('type must be');
    expect(() => validateManifest({ ...base, skills: { x: { type: 'local', contentHash: 'zz' } } })).toThrow('contentHash');
  });

  test('emptyManifest and emptyLocal have the expected shape', () => {
    expect(emptyManifest()).toEqual({ version: 1, skills: {}, superskills: {} });
    expect(emptyLocal()).toEqual({ disabled: [] });
  });
});

describe('listSkills', () => {
  test('lists skills and superskills, skipping folders without SKILL.md', () => {
    addSkill(sb.repo, 'alpha', 'first');
    addSkill(sb.repo, 'bundle', 'squashed', {}, 'superskills');
    fs.mkdirSync(path.join(sb.repo.skillsDir, 'not-a-skill'));
    expect(listSkills(sb.repo).map((s) => `${s.root}/${s.name}`)).toEqual(['skills/alpha', 'superskills/bundle']);
  });

  test('rejects one name in both skills/ and superskills/', () => {
    addSkill(sb.repo, 'dup', 'one');
    addSkill(sb.repo, 'dup', 'two', {}, 'superskills');
    expect(() => listSkills(sb.repo)).toThrow('two skills both named "dup"');
  });
});

describe('README table', () => {
  test('orders bundles, local skills, upstream sources, then unsourced skills', () => {
    const skills = [
      { name: 'loose', root: 'skills' as const, abs: '', description: 'no lock entry' },
      { name: 'mine', root: 'skills' as const, abs: '', description: 'local one' },
      { name: 'pulled', root: 'skills' as const, abs: '', description: 'vendored' },
      { name: 'bundle', root: 'superskills' as const, abs: '', description: 'squash' },
    ];
    const lock: Lock = { pulled: { source: 'o/r' }, mine: { source: 'quantavil/my-skills', sourceType: 'local' } };
    const manifest: Manifest = {
      version: 1,
      skills: { mine: { type: 'local', contentHash: 'a'.repeat(64) } },
      superskills: {},
    };
    const md = buildMarkdown(skills, lock, manifest);
    expect(md.indexOf('Bundles (load guides on demand)')).toBeLessThan(md.indexOf('### Local'));
    expect(md.indexOf('### Local')).toBeLessThan(md.indexOf('[o/r]'));
    expect(md.indexOf('[o/r]')).toBeLessThan(md.indexOf(`### ${UNSOURCED}`));
    expect(md).toContain('| `bundle` |');
    expect(md).not.toContain('(superskills/');
    expect(md).toContain('(skills/mine/)');
  });

  test('a superskill member is named under its bundle, not repeated in its source section', () => {
    const skills = [
      { name: 'member', root: 'skills' as const, abs: '', description: 'hidden by the bundle' },
      { name: 'bundle', root: 'superskills' as const, abs: '', description: 'squash' },
    ];
    const lock: Lock = { member: { source: 'o/r' } };
    const manifest: Manifest = {
      version: 1,
      skills: {},
      superskills: { bundle: { members: ['member'], description: '' } },
    };
    const md = buildMarkdown(skills, lock, manifest);
    expect(md).not.toContain('| [`member`]');
    expect(md).toContain('Members of `bundle`: `member`.');
  });

  test('render swaps the block and keeps $& literal', () => {
    const out = render('a\n<!-- skills:start -->\nold\n<!-- skills:end -->\nb', 'TABLE $& text');
    expect(out).toContain('TABLE $& text');
    expect(sourceLink({ source: 'a/b' })).toBe('[a/b](https://github.com/a/b)');
    expect(() => render('no markers', 'x')).toThrow('missing');
  });
});

describe('superskill build', () => {
  test('builds deterministic routers with valid frontmatter and copied member files', () => {
    addSkill(sb.repo, 'alpha', 'Alpha: does things', { 'references/api.md': '# API\n' });
    addSkill(sb.repo, 'beta', 'Beta | pipes and colons: ok');
    fs.writeFileSync(
      path.join(sb.repo.skillsDir, 'alpha/SKILL.md'),
      skillText('alpha', 'Alpha: does things', '# Alpha\n\nRead [the API](references/api.md).\n'),
    );
    const skills = listSkills(sb.repo);
    const def = { members: ['alpha', 'beta'], description: '' };
    const first = buildSuperFiles('bundle', def, resolveMembers(skills, def.members, 'bundle'));
    const second = buildSuperFiles('bundle', def, resolveMembers(skills, def.members, 'bundle'));
    expect(hashFiles(first)).toBe(hashFiles(second));

    const skillMd = first.find((f) => f.rel === 'SKILL.md')!.buf.toString();
    const fm = parseFrontmatter(skillMd);
    expect(fm.name).toBe('bundle');
    expect(fm.description).toContain('Beta | pipes');
    expect(skillMd).toContain('(alpha/GUIDE.md)');
    expect(skillMd).not.toContain('# Alpha');
    expect(first.find(f => f.rel === 'alpha/GUIDE.md')!.buf.toString()).toContain('(references/api.md)');
    expect(first.map((f) => f.rel)).toContain('alpha/references/api.md');
  });

  test('member guides keep relative links and stay outside the router body', () => {
    addSkill(sb.repo, 'alpha', 'Alpha does a thing', { 'references/api.md': '# API\n' });
    addSkill(sb.repo, 'beta', 'Beta | does another');
    fs.writeFileSync(path.join(sb.repo.skillsDir, 'alpha/SKILL.md'), skillText('alpha', 'Alpha does a thing', '# Alpha\n\nRead [the API](references/api.md).\n'));
    const skills = listSkills(sb.repo);
    const def = { members: ['alpha', 'beta'], description: 'router for alpha and beta' };
    const files = buildSuperFiles('router', def, resolveMembers(skills, def.members, 'router'));
    const rels = files.map((f) => f.rel).sort();
    expect(rels).toEqual(['SKILL.md', 'alpha/GUIDE.md', 'alpha/references/api.md', 'beta/GUIDE.md']);
    const skillMd = files.find((f) => f.rel === 'SKILL.md')!.buf.toString();
    expect(parseFrontmatter(skillMd).name).toBe('router');
    expect(skillMd).toContain('| [alpha](alpha/GUIDE.md) | Alpha does a thing |');
    expect(skillMd).toContain('Beta \\| does another');
    expect(skillMd).not.toContain('# Alpha');
    const guide = files.find((f) => f.rel === 'alpha/GUIDE.md')!.buf.toString();
    expect(guide).toContain('(references/api.md)');
    expect(guide.startsWith('---')).toBe(false);
  });

  test('a generated description is refused when it would give each member almost nothing', () => {
    for (let i = 0; i < 12; i++) addSkill(sb.repo, `s${String(i).padStart(2, '0')}`, `skill ${i}`);
    const skills = listSkills(sb.repo);
    const names = skills.map((s) => s.name);
    const def = { members: names, description: '' };
    expect(() => buildSuperFiles('many', def, resolveMembers(skills, names, 'many'))).toThrow('Pass --description');
    expect(() => buildSuperFiles('many', { ...def, description: 'explicit' }, resolveMembers(skills, names, 'many'))).not.toThrow();
  });

  test('refuses to nest superskills and to build with no members', () => {
    addSkill(sb.repo, 'inner', 'inner', {}, 'superskills');
    const skills = listSkills(sb.repo);
    expect(() => resolveMembers(skills, ['inner'], 'outer')).toThrow('cannot nest');
    expect(() => buildSuperFiles('empty', { members: [], description: '' }, [])).toThrow('at least one member');
  });

  test('generatedDescription stays within 1024 characters and gives every member a share', () => {
    addSkill(sb.repo, 'long', 'x'.repeat(1000));
    addSkill(sb.repo, 'longer', 'y'.repeat(1000));
    addSkill(sb.repo, 'tail', 'tail trigger words');
    const skills = listSkills(sb.repo).filter((s) => s.root === 'skills');
    const text = generatedDescription(skills);
    expect(text.length).toBeLessThanOrEqual(1024);
    expect(text).toContain('tail: tail trigger words');
  });
});
