// Bundles src/main.ts into one browser script and stamps it with a hash of the sources,
// so a stale copy stored in the browser can be spotted by comparing impexFill.version with VERSION in the build folder.
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { BUILD_DIR } from '../cli/config';

const files = readdirSync('src').sort();
const hash = createHash('sha256');
for (const file of files) hash.update(file).update(readFileSync(`src/${file}`));
const version = hash.digest('hex').slice(0, 10);

const result = await Bun.build({
  entrypoints: ['src/main.ts'],
  outdir: BUILD_DIR,
  naming: 'impexcube-fill.js',
  target: 'browser',
  format: 'iife',
  minify: true,
  define: { __VERSION__: JSON.stringify(version) },
});
if (!result.success) {
  for (const log of result.logs) console.error(log);
  process.exit(1);
}
await Bun.write(`${BUILD_DIR}/VERSION`, `${version}\n`);
console.log(
  `built ${BUILD_DIR}/impexcube-fill.js (${version}, ${Bun.file(`${BUILD_DIR}/impexcube-fill.js`).size / 1000} kB)`,
);
