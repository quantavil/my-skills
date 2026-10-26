// Prints one JavaScript statement for the browser pane: it stores the built bundle (default) or known.json
// in the page's localStorage, so nothing has to be encoded or escaped by hand.
//   bun run payload          -> stores the bundle, loads it, and returns its version
//   bun run payload known    -> stores known.json
import { BUILD_DIR } from '../cli/config';

const what = process.argv[2] ?? 'bundle';

if (what === 'bundle') {
  const code = await Bun.file(`${BUILD_DIR}/impexcube-fill.js`).text();
  console.log(
    `localStorage.setItem('ifBundle', ${JSON.stringify(code)}); (0, eval)(localStorage.ifBundle); impexFill.version`,
  );
} else if (what === 'known') {
  const known = JSON.stringify(await Bun.file(new URL('../known.json', import.meta.url)).json());
  console.log(`localStorage.setItem('ifKnown', ${JSON.stringify(known)}); localStorage.ifKnown.length`);
} else {
  console.error('Usage: bun run payload [bundle|known]');
  process.exit(2);
}
