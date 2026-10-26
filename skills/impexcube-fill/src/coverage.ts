// What a run did NOT look at. A pass only means the fields in the job file match, so every run also counts
// the other controls on the page that hold values, and names any control that is not in the known list.
export interface Control {
  id: string;
  value: string;
  filled: boolean;
}

const IGNORED_TYPES = new Set(['hidden', 'submit', 'button', 'image', 'reset', 'file', 'password']);
const GRID = 'table[id$="gvProductExp"], table[id$="gvrexport"]';
const GRID_ROW_ID = /_ctl\d+_|_\d+$/;

type Field = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

/** Every real form control on the page. Hidden state, buttons and grid rows are not controls we care about. */
export function scan(doc: Document = document): Control[] {
  const controls: Control[] = [];
  for (const field of doc.querySelectorAll<Field>('input, select, textarea')) {
    const { id } = field;
    if (!id || id.startsWith('__') || GRID_ROW_ID.test(id) || field.closest(GRID)) continue;
    if (IGNORED_TYPES.has(field.type.toLowerCase())) continue;
    const toggle = field instanceof HTMLInputElement && (field.type === 'checkbox' || field.type === 'radio');
    const filled = toggle
      ? field.checked
      : field instanceof HTMLSelectElement
        ? field.selectedIndex > 0
        : field.value.trim() !== '';
    controls.push({ id, value: toggle ? (filled ? 'on' : '') : field.value.trim(), filled });
  }
  return controls;
}

export const shortId = (id: string) => id.replace(/^ContentPlaceHolder1_/, '');

export interface Coverage {
  total: number;
  compared: number;
  /** controls that hold a value but were not compared against the job file */
  notCompared: Control[];
  /** controls that are neither compared nor in the known list: ImpexCube added them, or we never saw them.
   * null when no known list was given. */
  unknown: Control[] | null;
}

export function coverage(
  compared: ReadonlySet<string>,
  known: ReadonlySet<string> | undefined,
  doc: Document = document,
): Coverage {
  const controls = scan(doc);
  return {
    total: controls.length,
    compared: compared.size,
    notCompared: controls.filter((c) => c.filled && !compared.has(c.id)),
    unknown: known ? controls.filter((c) => !compared.has(c.id) && !known.has(shortId(c.id))) : null,
  };
}
