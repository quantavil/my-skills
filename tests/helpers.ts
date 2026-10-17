import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { repoAt, type Repo } from '../lib/repo';

export function skillText(name: string, description: string, body = '# Body\n'): string {
  return `---\nname: ${name}\ndescription: ${JSON.stringify(description)}\n---\n\n${body}`;
}

/** A throwaway repo and home. Nothing here touches the real checkout or the real agent folders. */
export function makeSandbox() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'my-skills-repo-'));
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'my-skills-home-'));
  fs.writeFileSync(path.join(root, 'README.md'), '# test\n\n<!-- skills:start -->\n<!-- skills:end -->\n');
  const repo: Repo = repoAt(root);
  return {
    repo,
    home,
    root,
    cleanup() {
      fs.rmSync(root, { recursive: true, force: true });
      fs.rmSync(home, { recursive: true, force: true });
    },
  };
}

/** Adds a skill folder under skills/ (or superskills/ with root = 'superskills'). */
export function addSkill(
  repo: Repo,
  name: string,
  description: string,
  files: Record<string, string> = {},
  root: 'skills' | 'superskills' = 'skills',
): void {
  const dir = path.join(root === 'skills' ? repo.skillsDir : repo.superDir, name);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'SKILL.md'), skillText(name, description));
  for (const [rel, body] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true });
    fs.writeFileSync(path.join(dir, rel), body);
  }
}

export function writeJson(file: string, data: unknown): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data, null, 2) + '\n');
}
