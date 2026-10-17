import fs from 'node:fs';
import path from 'node:path';
import { filesMatch, hashFiles, sourceHash } from './hash';
import { emptyManifest, readManifest, writeManifest, type Manifest } from './manifest';
import type { Repo } from './repo';
import { buildMarkdown, render } from './readme';
import { listSkills, sourceEntry, type SkillDir } from './skills';
import { buildSuperFiles, resolveMembers, writeSuper } from './superskill';
import { readLock, writeLock, type Lock } from './upstream';

const normalize = (s: string) => s.replace(/\r\n/g, '\n');

/** Brings derived state up to date: lock pins, skills.json, superskills and the README.
 *  Upstream hashes are never refreshed here, because that would hide local edits. */
export async function reindex(repo: Repo): Promise<string[]> {
  const notes: string[] = [];
  const existing = await readManifest(repo);
  const manifest: Manifest = existing ?? emptyManifest();
  const lock: Lock = await readLock(repo);
  let lockChanged = false;
  let manifestChanged = existing === null;

  relocateMembers(repo, manifest);
  const plain = listSkills(repo).filter((s) => s.root === 'skills');

  for (const s of plain) {
    if (!lock[s.name]) {
      lock[s.name] = {
        source: 'quantavil/my-skills',
        sourceType: 'local',
        skillPath: path.relative(repo.root, sourceEntry(s.abs)).split(path.sep).join('/'),
        computedHash: sourceHash(s.abs),
      };
      lockChanged = true;
      notes.push(`✓ pinned local skill "${s.name}"`);
    }
    if (lock[s.name]?.sourceType === 'local' && lock[s.name]?.source === 'quantavil/my-skills') {
      const localPath = path.relative(repo.root, sourceEntry(s.abs)).split(path.sep).join('/');
      if (lock[s.name]!.skillPath !== localPath) { lock[s.name]!.skillPath = localPath; lockChanged = true; }
    }
    if (!manifest.skills[s.name]) {
      const pinned = lock[s.name];
      const type = pinned && pinned.sourceType !== 'local' ? 'upstream' : 'local';
      manifest.skills[s.name] = { type, contentHash: sourceHash(s.abs) };
      manifestChanged = true;
      notes.push(`✓ "${s.name}" added to skills.json as ${type}`);
    }
    const meta = manifest.skills[s.name]!;
    if (meta.type === 'local') {
      const h = sourceHash(s.abs);
      if (h !== meta.contentHash) {
        meta.contentHash = h;
        manifestChanged = true;
      }
    }
  }

  for (const [name, def] of Object.entries(manifest.superskills)) {
    const members = resolveMembers(plain, def.members, name);
    const files = buildSuperFiles(name, def, members);
    const hash = hashFiles(files);
    const dir = path.join(repo.superDir, name);
    if (!filesMatch(dir, files)) {
      writeSuper(repo, name, files);
      notes.push(`✓ built superskill "${name}" from ${def.members.join(', ')}`);
    }
    const meta = manifest.skills[name] ?? { type: 'superskill', contentHash: hash };
    if (!manifest.skills[name] || meta.type !== 'superskill' || meta.contentHash !== hash) {
      meta.type = 'superskill';
      meta.contentHash = hash;
      manifestChanged = true;
    }
    manifest.skills[name] = meta;
  }

  const skills = listSkills(repo);
  const names = new Set(skills.map((s) => s.name));
  for (const name of Object.keys(manifest.skills)) {
    if (names.has(name)) continue;
    delete manifest.skills[name];
    delete manifest.superskills[name];
    manifestChanged = true;
    notes.push(`- "${name}" removed from skills.json (no folder)`);
  }

  if (lockChanged) await writeLock(repo, lock);
  if (manifestChanged) await writeManifest(repo, manifest);

  const before = normalize(await Bun.file(repo.readmePath).text());
  const after = normalize(render(before, buildMarkdown(skills, lock, manifest)));
  if (after !== before) {
    await Bun.write(repo.readmePath, after);
    notes.push(`✓ README.md regenerated (${skills.length} skills)`);
  }
  return notes;
}

/** True when README.md already matches what reindex would write. Read-only. */
export async function readmeMatches(repo: Repo, skills: SkillDir[], lock: Lock, manifest: Manifest): Promise<boolean> {
  const before = normalize(await Bun.file(repo.readmePath).text());
  return normalize(render(before, buildMarkdown(skills, lock, manifest))) === before;
}

/** Keep original member content once, as non-discoverable guides; restore removed members automatically. */
function relocateMembers(repo: Repo, manifest: Manifest): void {
  const members = new Set(Object.values(manifest.superskills).flatMap(def => def.members));
  const moves: Array<{ from: string; to: string; entry: string; renamed: string }> = [];
  for (const skill of listSkills(repo).filter(s => s.root === 'skills')) {
    const archive = members.has(skill.name);
    const to = path.join(archive ? repo.sourcesDir : repo.skillsDir, skill.name);
    if (skill.abs === to) continue;
    if (fs.existsSync(to)) throw new Error(`${skill.name}: both source and destination exist; refusing to overwrite`);
    const entry = path.join(skill.abs, archive ? 'SKILL.md' : 'GUIDE.md');
    const renamed = path.join(skill.abs, archive ? 'GUIDE.md' : 'SKILL.md');
    if (fs.existsSync(renamed)) throw new Error(`${skill.name}: ${path.basename(renamed)} already exists; cannot move source safely`);
    moves.push({ from: skill.abs, to, entry, renamed });
  }
  for (const move of moves) {
    fs.mkdirSync(path.dirname(move.to), { recursive: true });
    fs.renameSync(move.entry, move.renamed);
    try { fs.renameSync(move.from, move.to); }
    catch (err) { fs.renameSync(move.renamed, move.entry); throw err; }
  }
}
