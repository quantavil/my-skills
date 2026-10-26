// Starts the dedicated Chromium that the fill command drives. You log in to ImpexCube in it yourself.
import { spawn } from 'node:child_process';
import { BASE, CDP_URL, PORT, PROFILE_DIR } from './config';

async function debuggerUp(): Promise<boolean> {
  try {
    return (await fetch(`${CDP_URL}/json/version`, { signal: AbortSignal.timeout(1500) })).ok;
  } catch {
    return false;
  }
}

if (await debuggerUp()) {
  console.log(`Chromium is already running on port ${PORT}.`);
  process.exit(0);
}

const child = spawn(
  'chromium',
  [
    `--remote-debugging-port=${PORT}`,
    '--remote-debugging-address=127.0.0.1', // this machine only
    `--user-data-dir=${PROFILE_DIR}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--ozone-platform-hint=auto',
    BASE,
  ],
  { detached: true, stdio: 'ignore' },
);
child.unref();

for (let i = 0; i < 30; i++) {
  if (await debuggerUp()) {
    console.log(
      `Chromium started (profile ${PROFILE_DIR}). Log in to ImpexCube in its window, then run: bun run fill <job.json>`,
    );
    process.exit(0);
  }
  await Bun.sleep(500);
}
console.error('Chromium did not open its debugging port within 15 s.');
process.exit(2);
