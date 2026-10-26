// ImpexCube ends idle sessions. This tool never logs in (that stays with the user). It only notices a
// logged-out session, says so clearly, and speaks up when it keeps happening.
import { RunError } from './dom';

export const LOGOUT_LIMIT = 3;
const KEY = 'impexcube-fill:logouts';

export class LoggedOutError extends RunError {
  constructor() {
    super('ImpexCube is logged out. Ask the user to log in, then run again.');
  }
}

/** True when ImpexCube sends us to its login page. Reads one page and changes nothing. */
export async function isLoggedOut(): Promise<boolean> {
  try {
    const response = await fetch('/HomePage.aspx', { credentials: 'include' });
    return /frmlogin/i.test(response.url);
  } catch {
    return false;
  }
}

type Store = Pick<Storage, 'getItem' | 'setItem'>;

/** Counts logged-out stops in a row in this browser; any run that ends otherwise resets the count. */
export function recordSession(loggedOut: boolean, store: Store = localStorage): number {
  try {
    const count = loggedOut ? Number(store.getItem(KEY) ?? 0) + 1 : 0;
    store.setItem(KEY, String(count));
    return count;
  } catch {
    return loggedOut ? 1 : 0;
  }
}

export const logoutMessage = (count: number): string =>
  count >= LOGOUT_LIMIT
    ? `ImpexCube has logged out ${count} times in a row. Stop and tell the user that it keeps logging out ` +
      '(a login elsewhere or a short session timeout may be the cause); do not keep asking them to log in without saying so.'
    : new LoggedOutError().message;
