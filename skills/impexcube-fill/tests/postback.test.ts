import { beforeEach, describe, expect, test } from 'bun:test';
import { product } from '../src/fields';
import { postbackAfter, save, setField, whenIdle } from '../src/postback';
import { type FakeManager, installFakeSys } from './fake';

let fake: FakeManager;
beforeEach(() => {
  fake = installFakeSys();
  document.body.innerHTML = '';
});

describe('postbackAfter', () => {
  test('resolves true once the postback it started has finished', async () => {
    expect(await postbackAfter(() => fake.postback(10))).toBe(true);
    expect(fake.starts).toHaveLength(0);
    expect(fake.ends).toHaveLength(0);
  });

  test('rejects when no postback starts', async () => {
    await expect(postbackAfter(() => {}, { startWithinMs: 30 })).rejects.toThrow('did not start');
  });

  test('resolves false when optional and none starts', async () => {
    expect(await postbackAfter(() => {}, { optional: true, startWithinMs: 30 })).toBe(false);
  });

  test('reports a server error', async () => {
    await expect(postbackAfter(() => fake.postback(5, new Error('boom')))).rejects.toThrow('boom');
  });

  test('ignores the end of a postback it did not start', async () => {
    fake.inAsync = true;
    const later = whenIdle().then(() => postbackAfter(() => fake.postback(5)));
    setTimeout(() => {
      fake.inAsync = false;
    }, 40);
    expect(await later).toBe(true);
  });

  test('waits until the page is idle before it acts', async () => {
    fake.inAsync = true;
    let acted = false;
    const run = postbackAfter(() => {
      acted = true;
      fake.postback(5);
    });
    await Bun.sleep(30);
    expect(acted).toBe(false);
    fake.inAsync = false;
    await run;
    expect(acted).toBe(true);
  });
});

describe('save', () => {
  const button = (id: string, value: string) => {
    document.body.innerHTML = `<input type="submit" id="${id}" value="${value}">`;
    document.getElementById(id)?.addEventListener('click', () => fake.postback(5));
  };

  test('refuses a button that is not one of the four save buttons', () => {
    button('ContentPlaceHolder1_btnApprove', 'Update');
    expect(() => save('ContentPlaceHolder1_btnApprove')).toThrow('not a save button');
  });

  test('refuses an allowed id whose label is not Update', () => {
    button(product.save, 'Approve');
    expect(() => save(product.save)).toThrow('Refusing to click "Approve"');
  });

  test('clicks a real save button and waits for it', async () => {
    button(product.save, 'Update');
    expect(await save(product.save)).toBe(true);
  });
});

describe('setField', () => {
  test('does nothing when the value is already right', async () => {
    document.body.innerHTML = '<input id="a" value="x">';
    await setField('a', 'x');
    expect(fake.starts).toHaveLength(0);
  });

  test('sets a dropdown and waits for the postback it causes', async () => {
    document.body.innerHTML =
      '<select id="t"><option value="00">00</option><option value="99">99</option></select>';
    document.getElementById('t')?.addEventListener('change', () => fake.postback(10));
    await setField('t', '99');
    expect((document.getElementById('t') as HTMLSelectElement).value).toBe('99');
  });

  test('rejects a value the dropdown does not have', async () => {
    document.body.innerHTML = '<select id="t"><option value="00">00</option></select>';
    await expect(setField('t', '77')).rejects.toThrow('does not exist');
  });

  test('refuses a disabled field', async () => {
    document.body.innerHTML = '<input id="a" value="x" disabled>';
    await expect(setField('a', 'y')).rejects.toThrow('disabled');
  });
});
