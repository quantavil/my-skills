import { afterEach, describe, expect, test } from 'bun:test';
import { isLoggedOut, LOGOUT_LIMIT, logoutMessage, recordSession } from '../src/session';

const memory = () => {
  const data = new Map<string, string>();
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
  };
};

describe('recordSession', () => {
  test('counts logged-out stops in a row', () => {
    const store = memory();
    expect([recordSession(true, store), recordSession(true, store), recordSession(true, store)]).toEqual([
      1, 2, 3,
    ]);
  });

  test('any other outcome resets the count', () => {
    const store = memory();
    recordSession(true, store);
    recordSession(true, store);
    expect(recordSession(false, store)).toBe(0);
    expect(recordSession(true, store)).toBe(1);
  });

  test('still works when storage is blocked', () => {
    const blocked = {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
    };
    expect(recordSession(true, blocked)).toBe(1);
    expect(recordSession(false, blocked)).toBe(0);
  });
});

describe('logoutMessage', () => {
  test('asks the user to log in the first times', () => {
    expect(logoutMessage(1)).toContain('Ask the user to log in');
    expect(logoutMessage(LOGOUT_LIMIT - 1)).toContain('Ask the user to log in');
  });

  test('tells Claude to stop and tell the user after three in a row', () => {
    expect(logoutMessage(LOGOUT_LIMIT)).toContain('3 times in a row');
    expect(logoutMessage(LOGOUT_LIMIT)).toContain('tell the user');
  });
});

describe('isLoggedOut', () => {
  const realFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = realFetch;
  });
  const answer = (url: string) => {
    globalThis.fetch = (async () => ({ url })) as unknown as typeof fetch;
  };

  test('true when the site redirects to its login page', async () => {
    answer('https://export.impexcube.in/frmLogin.aspx');
    expect(await isLoggedOut()).toBe(true);
  });

  test('false on a normal page', async () => {
    answer('https://export.impexcube.in/HomePage.aspx');
    expect(await isLoggedOut()).toBe(false);
  });

  test('false when the network fails, so a network error is not reported as a logout', async () => {
    globalThis.fetch = (async () => {
      throw new Error('offline');
    }) as unknown as typeof fetch;
    expect(await isLoggedOut()).toBe(false);
  });
});
