import { expect, test } from 'bun:test';
import { runInThisContext } from 'node:vm';

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
  expect(version).toBe((await Bun.file(`${process.env.HOME}/.cache/impexcube-fill/VERSION`).text()).trim());
  expect(localStorage.ifBundle.length).toBeGreaterThan(10_000);
});
