#!/usr/bin/env bun
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { bundleDir, readConfig, repoAt, type Repo } from './lib/config';
import { build, bundleSkills, desiredLinks, syncBundle, treeHash } from './lib/bundles';
import { deploy } from './lib/deploy';
import { bundleTable, renderReadme } from './lib/readme';

const HELP = `my-skills: one skill library for every local agent

  ./run.sh                  build routers, find-skill and the README table (default)
  ./run.sh sync [bundle..]  re-download upstream bundles (all by default), then build
  ./run.sh deploy [--dry-run]   build, then link core bundles and find-skill into each target
  ./run.sh check            bundles.json valid, vendor/ complete, build and README current
  ./run.sh list             bundles with tier and skill count

Add or remove a bundle, or change its tier, by editing bundles.json, then run sync (new upstream) or deploy.`;

export function runBuild(repo: Repo): void {
  const config = readConfig(repo);
  build(repo, config);
  const readme = fs.readFileSync(repo.readmePath, 'utf8');
  const next = renderReadme(readme, bundleTable(repo, config));
  if (next !== readme) fs.writeFileSync(repo.readmePath, next);
}

/** Sync upstream bundles in parallel and delete vendor folders no bundle uses any more. */
export async function runSync(repo: Repo, only: string[]): Promise<void> {
  const config = readConfig(repo);
  for (const n of only) if (!config.bundles[n]?.repo) throw new Error(`${n} is not an upstream bundle in bundles.json`);
  const picked = Object.entries(config.bundles).filter(([name, b]) => b.repo && (!only.length || only.includes(name)));
  const results = await Promise.allSettled(picked.map(([name, b]) => syncBundle(repo, name, b)));
  const failed: string[] = [];
  results.forEach((r, i) => {
    const [name, b] = picked[i]!;
    if (r.status === 'fulfilled') console.log(`✓ ${name}: ${r.value} skills from ${b.repo}`);
    else failed.push((r.reason as Error).message);
  });
  if (failed.length) throw new Error(`sync failed:\n${failed.join('\n')}`);
  if (!only.length && fs.existsSync(repo.vendorDir)) {
    for (const dir of fs.readdirSync(repo.vendorDir)) {
      if (config.bundles[dir]?.repo) continue;
      fs.rmSync(path.join(repo.vendorDir, dir), { recursive: true, force: true });
      console.log(`- removed vendor/${dir} (not in bundles.json)`);
    }
  }
  runBuild(repo);
}

/** Problems a fresh build or sync would fix. Read-only: builds into a temporary folder. */
export function runCheck(repo: Repo): string[] {
  const config = readConfig(repo);
  const problems: string[] = [];
  const vendored = fs.existsSync(repo.vendorDir) ? fs.readdirSync(repo.vendorDir) : [];
  for (const dir of vendored) if (!config.bundles[dir]?.repo) problems.push(`vendor/${dir} is not in bundles.json (run sync)`);
  for (const [name, b] of Object.entries(config.bundles)) {
    if (bundleSkills(bundleDir(repo, name, b)).length === 0) problems.push(`${name}: no skills on disk${b.repo ? ' (run sync)' : ''}`);
  }
  if (problems.length) return problems;

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'my-skills-check-'));
  try {
    build(repo, config, tmp);
    if (treeHash(tmp) !== treeHash(repo.buildDir)) problems.push('.build/ is stale (run ./run.sh)');
  } catch (err) {
    problems.push((err as Error).message);
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  const readme = fs.readFileSync(repo.readmePath, 'utf8');
  if (!problems.length && renderReadme(readme, bundleTable(repo, config)) !== readme) problems.push('README.md table is stale (run ./run.sh)');
  return problems;
}

async function main(args: string[]): Promise<void> {
  const repo = repoAt(import.meta.dir);
  const [cmd = 'build', ...rest] = args;
  switch (cmd) {
    case 'build':
      return runBuild(repo);
    case 'sync':
      return runSync(repo, rest);
    case 'deploy': {
      const dryRun = rest.includes('--dry-run');
      if (!dryRun) runBuild(repo);
      const config = readConfig(repo);
      for (const line of deploy(repo, os.homedir(), config.targets, desiredLinks(repo, config), dryRun)) console.log(line);
      return;
    }
    case 'check': {
      const problems = runCheck(repo);
      for (const p of problems) console.error(`✗ ${p}`);
      if (problems.length) process.exit(1);
      return console.log('✓ bundles, build and README are current');
    }
    case 'list': {
      for (const [name, b] of Object.entries(readConfig(repo).bundles)) {
        const n = bundleSkills(bundleDir(repo, name, b)).length;
        console.log(`${b.tier.padEnd(8)} ${name.padEnd(24)} ${String(n).padStart(3)} skills  ${b.repo ?? 'local'}`);
      }
      return;
    }
    case 'help':
    case '--help':
    case '-h':
      return console.log(HELP);
    default:
      throw new Error(`unknown command "${cmd}"\n\n${HELP}`);
  }
}

if (import.meta.main) {
  try {
    await main(Bun.argv.slice(2));
  } catch (err) {
    console.error(`✗ ${(err as Error).message}`);
    process.exit(1);
  }
}
