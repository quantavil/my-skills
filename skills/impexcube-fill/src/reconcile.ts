// Compare a page with the job file, and fix only what differs.
import { RunError, read } from './dom';
import { save, setField } from './postback';

export type Log = (line: string, differs?: boolean) => void;

export interface Context {
  /** false: only look and report. true: fix, save and confirm. */
  apply: boolean;
  log: Log;
  /** ids of every field this step compared, for the coverage line */
  compared: Set<string>;
}

export interface Spec {
  label: string;
  id: string;
  want: string;
  kind: 'text' | 'num';
}

const toNumber = (value: string): number | null => {
  const clean = value.replace(/,/g, '').trim();
  if (clean === '') return null;
  const number = Number(clean);
  return Number.isFinite(number) ? number : null;
};

/** Numbers compare by value (2240.000 equals 2240); a blank field is never a number. */
export function same(kind: Spec['kind'], have: string, want: string): boolean {
  if (kind === 'text') return have === want;
  const a = toNumber(have);
  const b = toNumber(want);
  return a !== null && b !== null && Math.abs(a - b) < 0.005;
}

export const differences = (specs: readonly Spec[], current: (id: string) => string = read): Spec[] =>
  specs.filter((spec) => !same(spec.kind, current(spec.id), spec.want));

export const describe = (specs: readonly Spec[]): string =>
  specs.map((spec) => `${spec.label}: "${read(spec.id)}" -> "${spec.want}"`).join('; ');

/** Sets every differing field, in the order given, and proves none was wiped by a postback. */
async function fill(specs: readonly Spec[]): Promise<void> {
  for (let pass = 0; pass < 2; pass++) {
    for (const spec of differences(specs)) await setField(spec.id, spec.want);
    if (differences(specs).length === 0) return;
  }
  throw new RunError(
    `Could not set: ${differences(specs)
      .map((s) => s.label)
      .join(', ')}`,
  );
}

/**
 * Check one group of fields. With `apply`, fix them, save, then call `confirm`, which must reload the
 * state from the server and return whatever still differs. A failed confirmation stops the whole run.
 */
export async function reconcile(
  tag: string,
  specs: readonly Spec[],
  saveId: string,
  { apply, log, compared }: Context,
  confirm: () => Promise<Spec[]>,
): Promise<void> {
  for (const spec of specs) compared.add(spec.id);
  const diff = differences(specs);
  if (diff.length === 0) return log(`${tag}: correct`);
  log(`${tag}: ${describe(diff)}`, true);
  if (!apply) return;
  await fill(specs);
  await save(saveId);
  const left = await confirm();
  if (left.length > 0) {
    throw new RunError(
      `${tag}: NOT SAVED (${left.map((s) => s.label).join(', ')} still differ after saving)`,
    );
  }
  log(`${tag}: saved`);
}
