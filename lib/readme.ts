import type { Manifest } from './manifest';
import type { SkillDir } from './skills';
import type { Lock, LockEntry } from './upstream';

export const START = '<!-- skills:start -->';
export const END = '<!-- skills:end -->';
export const UNSOURCED = 'Unsourced';

/** Collapse whitespace and escape pipes so a description can't break the table. */
export function cell(s: string): string {
  return s.replace(/\s+/g, ' ').replace(/\|/g, '\\|').trim();
}

export function sourceLink(e?: LockEntry): string {
  if (!e) return UNSOURCED;
  const url = e.sourceUrl ?? (/^[\w.-]+\/[\w.-]+$/.test(e.source) ? `https://github.com/${e.source}` : null);
  return url ? `[${e.source}](${url})` : e.source;
}

/** Swap the block between the markers. Replacement is a function so `$&` in a description is literal. */
export function render(readme: string, table: string): string {
  const re = new RegExp(`${START}[\\s\\S]*?${END}`);
  if (!re.test(readme)) throw new Error(`README.md is missing the ${START} / ${END} markers`);
  return readme.replace(re, () => `${START}\n\n${table}\n\n${END}`);
}

/** Under the super skills table, name the member skills each bundle hides. */
function superNotes(manifest: Manifest): string[] {
  return Object.entries(manifest.superskills).map(
    ([sup, def]) => `\nMembers of \`${sup}\`: ${def.members.map((m) => `\`${m}\``).join(', ')}.`,
  );
}

/** Super skills first, then local skills, then upstream by repo, unsourced last. */
export function buildMarkdown(skills: SkillDir[], lock: Lock, manifest: Manifest): string {
  interface Group {
    rank: number;
    sort: string;
    heading: string;
    skills: SkillDir[];
  }
  const groups = new Map<string, Group>();
  const place = (key: string, rank: number, sort: string, heading: string, s: SkillDir) => {
    const g = groups.get(key) ?? { rank, sort, heading, skills: [] };
    g.skills.push(s);
    groups.set(key, g);
  };

  // A member is listed under its superskill, not again under its source repo.
  const memberOf = new Set(Object.values(manifest.superskills).flatMap((def) => def.members));

  for (const s of skills) {
    const meta = manifest.skills[s.name];
    if (s.root === 'skills' && memberOf.has(s.name)) continue;
    if (s.root === 'superskills') {
      place('super', 0, '', 'Bundles (load guides on demand)', s);
    } else if (meta?.type === 'local') {
      place('local', 1, '', 'Local', s);
    } else {
      const entry = lock[s.name];
      const source = entry?.source ?? UNSOURCED;
      place(`up:${source}`, source === UNSOURCED ? 3 : 2, source, sourceLink(entry), s);
    }
  }

  return [...groups.values()]
    .sort((a, b) => a.rank - b.rank || a.sort.localeCompare(b.sort))
    .map((g) => {
      const rows = g.skills
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((s) => `| ${s.root === 'skills' ? `[\`${s.name}\`](skills/${s.name}/)` : `\`${s.name}\``} | ${cell(s.description)} |`);
      const notes = g.rank === 0 ? superNotes(manifest) : [];
      return [`### ${g.heading}`, '', '| Skill | Use it when |', '| --- | --- |', ...rows, ...notes].join('\n');
    })
    .join('\n\n');
}
