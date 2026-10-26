import { beforeEach, describe, expect, test } from 'bun:test';
import * as f from '../src/fields';
import { syncItems, syncShipment } from '../src/pages';
import { type Job, parseJob } from '../src/schema';
import { type FakeManager, installFakeSys } from './fake';

const golden = parseJob(await Bun.file(new URL('./fixtures/sample-job.json', import.meta.url)).text());
let fake: FakeManager;
beforeEach(() => {
  fake = installFakeSys();
});

const run = async (sync: typeof syncShipment, apply = false, job: Job = golden) => {
  const lines: string[] = [];
  let differences = 0;
  await sync(job, {
    compared: new Set(),
    apply,
    log: (line, differs) => {
      lines.push(line);
      if (differs) differences++;
    },
  });
  return { lines, differences };
};

describe('job number guard', () => {
  test('stops when the page shows no job number', async () => {
    document.body.innerHTML = `<textarea id="${f.shipment.marksAndNos}"></textarea>`;
    await expect(run(syncShipment)).rejects.toThrow('Cannot see a job number');
  });

  test('stops when the page shows another job', async () => {
    document.body.innerHTML = `<input type="text" value="EXP-2627-999"><textarea id="${f.shipment.marksAndNos}"></textarea>`;
    await expect(run(syncShipment)).rejects.toThrow('EXP-2627-999');
  });

  test('stops when the page shows two jobs', async () => {
    document.body.innerHTML = `<input type="text" value="EXP-2627-123"><input type="text" value="EXP-2627-999"><textarea id="${f.shipment.marksAndNos}"></textarea>`;
    await expect(run(syncShipment)).rejects.toThrow('EXP-2627-999');
  });
});

describe('syncShipment (check)', () => {
  const page = (marks: string) => {
    document.body.innerHTML = `<input type="text" value="EXP-2627-123"><textarea id="${f.shipment.marksAndNos}">${marks}</textarea>`;
  };

  test('reports a wrong remark', async () => {
    page('OLD TEXT');
    const { lines, differences } = await run(syncShipment);
    expect(differences).toBe(1);
    expect(lines[0]).toContain('Marks & Nos');
  });

  test('is quiet when the remark is right', async () => {
    page(golden.shipment?.marksAndNos ?? '');
    const { lines, differences } = await run(syncShipment);
    expect(differences).toBe(0);
    expect(lines).toEqual(['Shipment: correct']);
  });
});

describe('syncItems', () => {
  const noGrid = (options: string) => {
    document.body.innerHTML = `<input type="text" value="EXP-2627-123"><input id="${f.product.description}">
      <select id="${f.product.invoice}"><option value="">--Choose--</option>${options}</select>`;
    document.getElementById(f.product.invoice)?.addEventListener('change', () => {
      fake.postback(5);
      setTimeout(() => {
        const grid = document.createElement('table');
        grid.id = f.product.gridElement;
        document.body.append(grid);
        // the real page would now render the form for row 1
        document.body.insertAdjacentHTML('beforeend', `<input id="${f.product.sno}" value="9">`);
      }, 1);
    });
    Object.assign(globalThis, { __doPostBack: () => fake.postback(5) });
  };

  test('picks the only invoice when the grid is missing', async () => {
    noGrid('<option value="INV/1">INV/1</option>');
    await expect(run(syncItems, false, { ...golden, invoiceNo: undefined })).rejects.toThrow('shows S.No 9');
    expect((document.getElementById(f.product.invoice) as HTMLSelectElement).value).toBe('INV/1');
  });

  test('refuses to guess between several invoices', async () => {
    noGrid('<option value="A">A</option><option value="B">B</option>');
    await expect(run(syncItems, false, { ...golden, invoiceNo: undefined })).rejects.toThrow('invoiceNo');
  });

  test('stops when the grid row shows another item', async () => {
    document.body.innerHTML = `<input type="text" value="EXP-2627-123"><input id="${f.product.description}"><table id="${f.product.gridElement}"></table><input id="${f.product.sno}" value="7">`;
    Object.assign(globalThis, { __doPostBack: () => fake.postback(5) });
    await expect(run(syncItems)).rejects.toThrow('shows S.No 7, not 1');
  });
});
