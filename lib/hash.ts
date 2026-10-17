import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

export interface FileEntry {
  rel: string;
  buf: Buffer;
  /** Preserve script permissions when building bundles. */
  mode?: number;
}

/** Generated and VCS junk. It must not count as skill content, or running a skill's scripts would change its hash. */
const JUNK_DIRS = new Set(['.git', 'node_modules', '__pycache__', '.venv', '.pytest_cache']);
const JUNK_FILES = /\.pyc$|^\.DS_Store$/;

/** Every file under `dir` as a forward-slash path relative to it, junk excluded. */
export function collectFiles(dir: string, cur = dir, out: FileEntry[] = []): FileEntry[] {
  for (const e of fs.readdirSync(cur, { withFileTypes: true })) {
    const full = path.join(cur, e.name);
    if (e.isDirectory()) {
      if (JUNK_DIRS.has(e.name)) continue;
      collectFiles(dir, full, out);
    } else if (e.isFile() && !JUNK_FILES.test(e.name)) {
      out.push({ rel: path.relative(dir, full).split(path.sep).join('/'), buf: fs.readFileSync(full), mode: fs.statSync(full).mode & 0o777 });
    }
  }
  return out;
}

/** Same algorithm as the skills CLI's folder hash, so a hash here can be checked against its lock. */
export function hashFiles(files: FileEntry[]): string {
  const h = createHash('sha256');
  for (const f of [...files].sort((a, b) => a.rel.localeCompare(b.rel))) {
    h.update(f.rel);
    h.update(f.buf);
  }
  return h.digest('hex');
}

export function folderHash(dir: string): string {
  return hashFiles(collectFiles(dir));
}

/** Content hashes remain compatible with upstream; executable permissions are checked separately. */
export function filesMatch(dir: string, files: FileEntry[]): boolean {
  if (!fs.existsSync(dir) || folderHash(dir) !== hashFiles(files)) return false;
  return process.platform === 'win32' || files.every(f => f.mode === undefined ||
    (fs.statSync(path.join(dir, f.rel)).mode & 0o111) === (f.mode & 0o111));
}

/** Source archives use GUIDE.md so scanners cannot discover bundle members. Hash the original filename. */
export function sourceFiles(dir: string): FileEntry[] {
  const archived = !fs.existsSync(path.join(dir, 'SKILL.md')) && fs.existsSync(path.join(dir, 'GUIDE.md'));
  return collectFiles(dir).map(f => archived && f.rel === 'GUIDE.md' ? { ...f, rel: 'SKILL.md' } : f);
}

export function sourceHash(dir: string): string {
  return hashFiles(sourceFiles(dir));
}
