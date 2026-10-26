import { beforeAll, expect, test } from 'bun:test';
import { runInThisContext } from 'node:vm';
import { BUILD_DIR } from '../cli/config';

// the payload reads the built bundle, so build it first (CI starts without one)
beforeAll(async () => {
  const build = Bun.spawn(['bun', 'scripts/build.ts'], { stdout: 'ignore', stderr: 'inherit' });
  expect(await build.exited).toBe(0);
});

const payload = async (what?: string) => {
  const run = Bun.spawn(['bun', 'scripts/payload.ts', ...(what ? [what] : [])], {
    stdout: 'pipe',
    stderr: 'pipe',
  });
  return await new Response(run.stdout).text();
};

test('the known payload stores the list for all three steps', async () => {
  localStorage.clear();
  const stored = runInThisContext(await payload('known'));
  expect(stored).toBeGreaterThan(1000);
  expect(Object.keys(JSON.parse(localStorage.ifKnown)).sort()).toEqual(['items', 'job', 'shipment']);
});

test('the bundle payload stores the bundle, loads it and returns its version', async () => {
  localStorage.clear();
  const version = runInThisContext(await payload());
  expect(version).toBe((await Bun.file(`${BUILD_DIR}/VERSION`).text()).trim());
  expect(localStorage.ifBundle.length).toBeGreaterThan(10_000);
});
