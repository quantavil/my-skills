// Entry points. runAll checks or fills a whole job from one page; each step runs inside a hidden
// same-origin frame, so the caller needs no navigation and one call covers the job.
import { coverage, scan, shortId } from './coverage';
import { RunError, sleep } from './dom';
import { STEPS, type Step, type StepName } from './fields';
import { type Sync, syncItems, syncJobDetails, syncShipment } from './pages';
import type { Log } from './reconcile';
import { parseJob } from './schema';
import { isLoggedOut, LoggedOutError, logoutMessage, recordSession } from './session';

declare const __VERSION__: string;
export const VERSION = typeof __VERSION__ === 'undefined' ? 'dev' : __VERSION__;

const SYNC: Record<StepName, Sync> = { job: syncJobDetails, shipment: syncShipment, items: syncItems };

export interface RunOptions {
  /** run one step only (Job Details is always opened) */
  only?: StepName;
  /** also list every field that holds a value but was not compared */
  audit?: boolean;
  /** control ids already seen per step (known.json); without it, new controls are not reported */
  known?: Partial<Record<StepName, string[]>>;
}

export interface StepCoverage {
  compared: number;
  notCompared: number;
  /** ids (without the ContentPlaceHolder1_ prefix) that are in no known list */
  unknown: string[];
}

const cut = (value: string) => (value.length > 60 ? `${value.slice(0, 60)}...` : value);

/**
 * Runs inside an ImpexCube page: one step of the job, then says how much of the page it did not look at.
 * With `audit`, every field that holds a value but was not compared is listed.
 */
export async function runStep(
  name: StepName,
  jobJson: string,
  apply: boolean,
  log: Log,
  { audit = false, known }: RunOptions = {},
): Promise<StepCoverage> {
  const compared = new Set<string>();
  await SYNC[name](parseJob(jobJson), { apply, log, compared });
  const knownIds = known?.[name] ? new Set(known[name]) : undefined;
  const seen = coverage(compared, knownIds);
  log(
    `compared ${seen.compared} of ${seen.total} fields; ${seen.notCompared.length} others hold values and were not compared`,
  );
  if (!seen.unknown) log('no known.json given, so new controls were not checked');
  for (const control of seen.unknown ?? []) {
    log(`NEW, not in known.json: ${shortId(control.id)} = "${cut(control.value)}"`, true);
  }
  if (audit) for (const c of seen.notCompared) log(`  not compared: ${shortId(c.id)} = "${cut(c.value)}"`);
  return {
    compared: seen.compared,
    notCompared: seen.notCompared.length,
    unknown: (seen.unknown ?? []).map((c) => shortId(c.id)),
  };
}

export interface Progress {
  version: string;
  lines: string[];
  differences: number;
  /** fields compared against the job file, and other fields holding values that were not */
  compared: number;
  notCompared: number;
  /** step name -> ids that are in no known list */
  unknown: Record<string, string[]>;
  /** logged-out stops in a row in this browser; 0 when this run did not stop that way */
  logouts: number;
  ok: boolean;
  done: boolean;
}

type FrameWindow = Window & { eval(code: string): unknown; Sys?: unknown; impexFill: typeof api };

const STEP_LIMIT_MS = 5 * 60_000;

function timeout<T>(work: Promise<T>, ms: number, what: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  const limit = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new RunError(`${what} took longer than ${ms / 1000} s`)), ms);
  });
  return Promise.race([work, limit]).finally(() => clearTimeout(timer));
}

/** Loads a page in a hidden frame and waits until its form is usable. */
async function openFrame(step: Step, jobNo: string): Promise<HTMLIFrameElement> {
  const frame = document.createElement('iframe');
  frame.style.cssText = 'position:fixed;left:-10000px;top:0;width:1200px;height:900px;border:0';
  document.body.append(frame);
  try {
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => reject(new RunError(`${step.label} did not load in 20 s`)), 20_000);
      frame.addEventListener(
        'load',
        () => {
          clearTimeout(timer);
          resolve();
        },
        { once: true },
      );
      frame.src = `/${step.path(jobNo)}`;
    });
    const win = frame.contentWindow as FrameWindow;
    if (/frmlogin/i.test(win.location.pathname)) {
      throw new LoggedOutError();
    }
    for (let i = 0; i < 100; i++) {
      if (win.document.getElementById(step.ready) && win.Sys) return frame;
      await sleep(100);
    }
    throw new RunError(`The ${step.label} form did not appear`);
  } catch (error) {
    frame.remove();
    throw error;
  }
}

/**
 * Checks (apply = false) or fixes (apply = true) a whole job. `bundle` is this script's own source,
 * evaluated inside each frame. Progress is published on window.__impexProgress so a caller can poll it.
 */
export async function runAll(
  jobJson: string,
  apply: boolean,
  bundle: string,
  options: RunOptions = {},
): Promise<Progress> {
  const { only } = options;
  const w = window as unknown as { __impexProgress?: Progress };
  if (w.__impexProgress && !w.__impexProgress.done) {
    return { ...w.__impexProgress, ok: false, lines: ['STOPPED: a run is already in progress'] };
  }
  const progress: Progress = {
    version: VERSION,
    lines: [],
    differences: 0,
    compared: 0,
    notCompared: 0,
    unknown: {},
    logouts: 0,
    ok: true,
    done: false,
  };
  w.__impexProgress = progress;
  const log: Log = (line, differs) => {
    progress.lines.push(`  ${line}`);
    if (differs) progress.differences++;
  };
  try {
    if (only && !STEPS.some((s) => s.name === only)) throw new RunError(`Unknown step "${only}"`);
    const job = parseJob(jobJson);
    for (const step of STEPS) {
      const wanted = !only || only === step.name;
      // Job Details is always opened: that is what tells ImpexCube which job the other pages show.
      if (!wanted && step.name !== 'job') continue;
      progress.lines.push(`${step.label}:`);
      const frame = await openFrame(step, job.jobNo);
      try {
        if (!wanted) continue;
        const win = frame.contentWindow as FrameWindow;
        win.eval(bundle);
        const reloaded = new Promise<never>((_, reject) => {
          frame.addEventListener(
            'load',
            () => reject(new RunError('The page reloaded during the step (a full postback). Stopped.')),
            {
              once: true,
            },
          );
        });
        reloaded.catch(() => {});
        const seen = await timeout(
          Promise.race([win.impexFill.runStep(step.name, jobJson, apply, log, options), reloaded]),
          STEP_LIMIT_MS,
          step.label,
        );
        progress.compared += seen.compared;
        progress.notCompared += seen.notCompared;
        progress.unknown[step.name] = seen.unknown;
      } finally {
        frame.remove();
      }
    }
    recordSession(false);
  } catch (error) {
    progress.ok = false;
    // A stop from an expired session can look like any page error, so ask the site before blaming the page.
    if (error instanceof LoggedOutError || (await isLoggedOut())) {
      progress.logouts = recordSession(true);
      progress.lines.push(`STOPPED: ${logoutMessage(progress.logouts)}`);
    } else {
      recordSession(false);
      progress.lines.push(`STOPPED: ${(error as Error).message}`);
    }
  }
  progress.lines.push(
    `Result: ${progress.differences} differences in ${progress.compared} compared fields. ` +
      `${progress.notCompared} other fields hold values that this tool does not check.`,
  );
  progress.done = true;
  return progress;
}

export const api = { version: VERSION, runAll, runStep, scan };
