/** A run stopped on purpose. The message is meant for the user. */
export class RunError extends Error {
  override name = 'RunError';
}

export const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export type Control = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

export function el<T extends HTMLElement = HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (!found) throw new RunError(`Field not found on this page: ${id}`);
  return found as T;
}

export const maybeEl = <T extends HTMLElement = HTMLElement>(id: string) =>
  document.getElementById(id) as T | null;

/** The value of a field as the page shows it now. */
export const read = (id: string): string => el<Control>(id).value.trim();

/**
 * Stops unless the page clearly shows the expected job number (and only that one).
 * Fails closed: a page with no visible job number is not trusted.
 */
export function requireJob(expected: string): void {
  const seen = new Set<string>();
  for (const input of document.querySelectorAll<HTMLInputElement>('input[type="text"]')) {
    const value = input.value.trim();
    if (/^EXP-\d{4}-\d+$/.test(value)) seen.add(value);
  }
  if (seen.size === 0) throw new RunError('Cannot see a job number on this page, so nothing was changed.');
  if (seen.size > 1 || !seen.has(expected)) {
    throw new RunError(
      `This page shows ${[...seen].join(', ')} but the file is for ${expected}. Nothing was changed.`,
    );
  }
}

/** Values as the server holds them now: the page fetched again, not the live form. */
export async function readFresh(ids: readonly string[]): Promise<Record<string, string>> {
  const response = await fetch(location.href, { credentials: 'include' });
  const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
  const values: Record<string, string> = {};
  for (const id of ids) {
    const control = doc.getElementById(id) as Control | null;
    if (control) values[id] = control.value.trim();
  }
  return values;
}
