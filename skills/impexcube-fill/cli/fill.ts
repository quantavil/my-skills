// bun run fill <job.json> [--apply] [--audit] [--only job|shipment|items]
// Attaches to the dedicated Chromium over CDP, opens a new tab, injects the built script and runs impexFill.runAll,
// the same call the browser-pane route uses. Exit code: 0 matches or fixed, 1 differences found, 2 error.
import { chromium } from 'playwright-core';
import { STEPS, type StepName } from '../src/fields';
import type {} from '../src/main'; // window.impexFill typing
import type { Progress, RunOptions } from '../src/run';
import { parseJob } from '../src/schema';
import { BASE, BUILD_DIR, CDP_URL } from './config';

const args = process.argv.slice(2);
const apply = args.includes('--apply');
const audit = args.includes('--audit');
const onlyAt = args.indexOf('--only');
const only = onlyAt >= 0 ? (args[onlyAt + 1] as StepName) : undefined;
const onlyValueAt = onlyAt >= 0 ? onlyAt + 1 : -1;
const jobPath = args.find((arg, i) => !arg.startsWith('--') && i !== onlyValueAt);

async function main(): Promise<number> {
  if (!jobPath || (only && !STEPS.some((s) => s.name === only))) {
    console.error('Usage: bun run fill <job.json> [--apply] [--audit] [--only job|shipment|items]');
    return 2;
  }
  const jobJson = await Bun.file(jobPath).text();
  const job = parseJob(jobJson);
  const known = await Bun.file(new URL('../known.json', import.meta.url)).json();
  const bundle = await Bun.file(`${BUILD_DIR}/impexcube-fill.js`).text();

  const browser = await chromium.connectOverCDP(CDP_URL).catch(() => null);
  if (!browser) {
    console.error('Cannot reach the Chromium. Start it with: bun run browser');
    return 2;
  }
  const context = browser.contexts()[0];
  const firstStep = STEPS[0];
  if (!context || !firstStep) throw new Error('The Chromium has no browser context');
  const page = await context.newPage(); // a new tab, so no open page loses unsaved work
  try {
    await page.goto(BASE + firstStep.path(job.jobNo), { waitUntil: 'load' });
    if (/frmlogin/i.test(page.url())) {
      console.error('ImpexCube is logged out. Log in in the Chromium window, then run again.');
      return 2;
    }
    await page.addScriptTag({ content: bundle });
    await page.evaluate(
      ([json, doApply, source, options]) => {
        void window.impexFill.runAll(
          json as string,
          doApply as boolean,
          source as string,
          options as RunOptions,
        );
      },
      [jobJson, apply, bundle, { only, audit, known }],
    );
    let printed = 0;
    for (;;) {
      await Bun.sleep(1000);
      const progress = (await page.evaluate(
        () => (window as unknown as { __impexProgress?: Progress }).__impexProgress,
      )) as Progress | undefined;
      if (!progress) continue;
      for (const line of progress.lines.slice(printed)) console.log(line);
      printed = progress.lines.length;
      if (!progress.done) continue;
      if (!progress.ok) return 2;
      console.log(
        apply
          ? `\nDone. ${progress.differences} difference(s) were fixed and confirmed. Open the Check List and review.`
          : progress.differences === 0
            ? '\nCheck passed: the job matches the file.'
            : `\nCheck found ${progress.differences} difference(s). Run again with --apply to fix them.`,
      );
      return !apply && progress.differences > 0 ? 1 : 0;
    }
  } finally {
    await page.close().catch(() => {});
    await browser.close(); // disconnects only; the Chromium keeps running
  }
}

main()
  .then((code) => process.exit(code))
  .catch((error) => {
    console.error(`STOPPED: ${(error as Error).message}`);
    process.exit(2);
  });
