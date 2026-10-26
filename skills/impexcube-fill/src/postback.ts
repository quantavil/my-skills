// Driving an ASP.NET WebForms page that uses UpdatePanels.
// Rules: wait until idle before acting, fire change events, wait for the postback the action started,
// and look elements up again afterwards (a postback replaces them).
import { type Control, el, maybeEl, RunError, sleep } from './dom';
import { reExport, SAVE_BUTTONS } from './fields';

interface EndArgs {
  get_error(): Error | null;
  set_errorHandled(handled: boolean): void;
}
type Handler = (sender: unknown, args: EndArgs) => void;
interface Manager {
  get_isInAsyncPostBack(): boolean;
  add_initializeRequest(handler: Handler): void;
  remove_initializeRequest(handler: Handler): void;
  add_endRequest(handler: Handler): void;
  remove_endRequest(handler: Handler): void;
}

declare const Sys: { WebForms: { PageRequestManager: { getInstance(): Manager } } };
declare function __doPostBack(target: string, argument: string): void;

const manager = () => Sys.WebForms.PageRequestManager.getInstance();

export async function whenIdle(timeoutMs = 20_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (manager().get_isInAsyncPostBack()) {
    if (Date.now() > deadline) throw new RunError('The page is still busy after 20 s');
    await sleep(50);
  }
}

export interface PostbackOptions {
  /** true: it is fine if the action starts no postback (resolves false) */
  optional?: boolean;
  startWithinMs?: number;
  timeoutMs?: number;
}

/** Runs `trigger` and resolves once the async postback that it started has finished. */
export async function postbackAfter(
  trigger: () => void,
  { optional = false, startWithinMs = 1500, timeoutMs = 20_000 }: PostbackOptions = {},
): Promise<boolean> {
  await whenIdle();
  const m = manager();
  return new Promise<boolean>((resolve, reject) => {
    let started = false;
    const finish = (done: () => void) => {
      clearTimeout(startTimer);
      clearTimeout(limitTimer);
      m.remove_initializeRequest(onStart);
      m.remove_endRequest(onEnd);
      done();
    };
    const onStart: Handler = () => {
      started = true;
      clearTimeout(startTimer);
    };
    const onEnd: Handler = (_sender, args) => {
      if (!started) return;
      const error = args.get_error();
      if (error) {
        args.set_errorHandled(true);
        finish(() => reject(new RunError(`The server reported an error: ${error.message}`)));
      } else {
        finish(() => setTimeout(() => resolve(true), 250));
      }
    };
    const startTimer = setTimeout(
      () =>
        finish(() =>
          optional
            ? resolve(false)
            : reject(new RunError('The page did not start the update that was expected')),
        ),
      startWithinMs,
    );
    const limitTimer = setTimeout(
      () => finish(() => reject(new RunError('Timed out waiting for the page update'))),
      timeoutMs,
    );
    m.add_initializeRequest(onStart);
    m.add_endRequest(onEnd);
    try {
      trigger();
    } catch (error) {
      finish(() => reject(error));
    }
  });
}

/** Sets a field and fires the events the server needs. Does nothing if the value is already right. */
export async function setField(id: string, value: string): Promise<void> {
  const control = el<Control>(id);
  if (control.disabled) throw new RunError(`Field is disabled: ${id}`);
  if (control.value === value) return;
  control.value = value;
  if (control instanceof HTMLSelectElement && control.value !== value) {
    throw new RunError(`Option "${value}" does not exist in ${id}`);
  }
  await postbackAfter(
    () => {
      control.dispatchEvent(new Event('input', { bubbles: true }));
      control.dispatchEvent(new Event('change', { bubbles: true }));
    },
    { optional: true, startWithinMs: 600 },
  );
}

/** Selects row `index` of a GridView, which is what its "Select" link does. */
export function selectRow(grid: string, index: number): Promise<boolean> {
  return postbackAfter(() => __doPostBack(grid, `Select$${index}`));
}

/** Clicks one of the four known save buttons. Nothing else can be clicked. */
export function save(buttonId: string): Promise<boolean> {
  if (!SAVE_BUTTONS.includes(buttonId))
    throw new RunError(`Refusing to click ${buttonId}: it is not a save button`);
  const button = el<HTMLInputElement>(buttonId);
  if (!/^update$/i.test(button.value)) throw new RunError(`Refusing to click "${button.value}"`);
  return postbackAfter(() => button.click());
}

export async function openReExportTab(): Promise<void> {
  await postbackAfter(() => maybeEl(reExport.tabHeader)?.click(), { optional: true, startWithinMs: 500 });
}
