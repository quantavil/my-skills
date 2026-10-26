import { homedir } from 'node:os';
import { join } from 'node:path';

export const BASE = 'https://export.impexcube.in/';
export const PORT = 9222;
/** Where `bun run build` writes the bundle. Outside the skill folder, so building never changes the skill's content hash. */
export const BUILD_DIR = join(process.env.XDG_CACHE_HOME ?? join(homedir(), '.cache'), 'impexcube-fill');
export const CDP_URL = `http://127.0.0.1:${PORT}`;
/** Separate profile, so your everyday browser is never touched. The login lives here. */
export const PROFILE_DIR = join(homedir(), '.local/share/impexcube-chromium');
