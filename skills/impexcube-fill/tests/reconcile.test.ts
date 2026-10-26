import { beforeEach, describe, expect, test } from 'bun:test';
import { product } from '../src/fields';
import { reconcile, type Spec, same } from '../src/reconcile';
import { type FakeManager, installFakeSys } from './fake';

let fake: FakeManager;
beforeEach(() => {
  fake = installFakeSys();
});

describe('same', () => {
  test('numbers compare by value', () => {
    expect(same('num', '2240.000', '2240')).toBe(true);
    expect(same('num', '995518.050000', '995518.05')).toBe(true);
    expect(same('num', '2240', '2000')).toBe(false);
  });

  test('a blank field is never equal to zero', () => {
    expect(same('num', '', '0')).toBe(false);
  });

  test('thousands separators are understood', () => {
    expect(same('num', '1,234.50', '1234.5')).toBe(true);
  });

  test('text compares exactly', () => {
    expect(same('text', 'NA', 'NA')).toBe(true);
    expect(same('text', 'NA ', 'NA')).toBe(false);
  });
});

describe('reconcile', () => {
  const page = () => {
    document.body.innerHTML = `<input id="a" value="old"><input type="submit" id="${product.save}" value="Update">`;
    document.getElementById(product.save)?.addEventListener('click', () => fake.postback(5));
  };
  const specs: Spec[] = [{ label: 'a', id: 'a', want: 'new', kind: 'text' }];

  test('check mode reports and changes nothing', async () => {
    page();
    const lines: [string, boolean | undefined][] = [];
    await reconcile(
      'T',
      specs,
      product.save,
      { apply: false, log: (l, d) => lines.push([l, d]), compared: new Set() },
      async () => [],
    );
    expect(lines).toEqual([['T: a: "old" -> "new"', true]]);
    expect((document.getElementById('a') as HTMLInputElement).value).toBe('old');
  });

  test('says correct when nothing differs', async () => {
    page();
    const lines: string[] = [];
    const same: Spec[] = [{ label: 'a', id: 'a', want: 'old', kind: 'text' }];
    await reconcile(
      'T',
      same,
      product.save,
      { apply: true, log: (l) => lines.push(l), compared: new Set() },
      async () => [],
    );
    expect(lines).toEqual(['T: correct']);
  });

  test('apply fixes, saves and confirms', async () => {
    page();
    const lines: string[] = [];
    await reconcile(
      'T',
      specs,
      product.save,
      { apply: true, log: (l) => lines.push(l), compared: new Set() },
      async () => [],
    );
    expect((document.getElementById('a') as HTMLInputElement).value).toBe('new');
    expect(lines.at(-1)).toBe('T: saved');
  });

  test('a failed confirmation stops the run', async () => {
    page();
    await expect(
      reconcile(
        'T',
        specs,
        product.save,
        { apply: true, log: () => {}, compared: new Set() },
        async () => specs,
      ),
    ).rejects.toThrow('NOT SAVED');
  });
});
