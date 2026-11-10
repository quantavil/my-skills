import { bundleDir, GITHUB_SLUG, type Config, type Repo } from './config';
import { bundleSkills } from './bundles';

const START = '<!-- bundles:start -->';
const END = '<!-- bundles:end -->';

export function bundleTable(repo: Repo, config: Config): string {
  const rows = Object.entries(config.bundles)
    .sort(([a, x], [b, y]) => x.tier.localeCompare(y.tier) || a.localeCompare(b))
    .map(([name, b]) => {
      const source = b.repo ? (GITHUB_SLUG.test(b.repo) ? `[${b.repo}](https://github.com/${b.repo})` : b.repo) : 'local';
      const n = bundleSkills(bundleDir(repo, name, b)).length;
      return `| \`${name}\` | ${b.tier} | ${n} | ${source} | ${b.summary.replace(/\|/g, '\\|')} |`;
    });
  return ['| Bundle | Tier | Skills | Source | Use for |', '| --- | --- | --- | --- | --- |', ...rows].join('\n');
}

/** README with the generated table swapped in between the markers. */
export function renderReadme(readme: string, table: string): string {
  const re = new RegExp(`${START}[\\s\\S]*?${END}`);
  if (!re.test(readme)) throw new Error(`README.md is missing the ${START} / ${END} markers`);
  return readme.replace(re, () => `${START}\n\n${table}\n\n${END}`);
}
