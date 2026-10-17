import path from 'node:path';

/** Every location the manager reads or writes, derived from one root. */
export interface Repo {
  root: string;
  skillsDir: string;
  superDir: string;
  /** Bundled source guides, outside skill discovery. */
  sourcesDir: string;
  /** Links to the enabled set. Gemini and OpenCode read this instead of skills/. */
  activeDir: string;
  lockPath: string;
  manifestPath: string;
  localPath: string;
  readmePath: string;
}

export function repoAt(root: string): Repo {
  return {
    root,
    skillsDir: path.join(root, 'skills'),
    superDir: path.join(root, 'superskills'),
    sourcesDir: path.join(root, 'sources'),
    activeDir: path.join(root, '.active'),
    lockPath: path.join(root, 'skills-lock.json'),
    manifestPath: path.join(root, 'skills.json'),
    localPath: path.join(root, 'skills.local.json'),
    readmePath: path.join(root, 'README.md'),
  };
}
