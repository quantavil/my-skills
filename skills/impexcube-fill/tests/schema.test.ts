import { describe, expect, test } from 'bun:test';
import { parseJob } from '../src/schema';

const golden = await Bun.file(new URL('./fixtures/sample-job.json', import.meta.url)).text();
// biome-ignore lint/suspicious/noExplicitAny: the tests edit arbitrary parts of the JSON on purpose
const edit = (change: (job: Record<string, any>) => void) => {
  const job = JSON.parse(golden);
  change(job);
  return JSON.stringify(job);
};

describe('parseJob', () => {
  test('accepts the real job file', () => {
    const job = parseJob(golden);
    expect(job.items).toHaveLength(10);
    expect(job.items.reduce((sum, item) => sum + item.qty, 0)).toBe(17816);
  });

  test('rejects text that is not JSON', () => {
    expect(() => parseJob('{oops')).toThrow('not valid JSON');
  });

  test('rejects a mistyped key instead of ignoring it', () => {
    expect(() => parseJob(edit((j) => (j.shipment = { marksAndNo: 'x' })))).toThrow('Job file problems');
  });

  test('rejects numbers where text is needed', () => {
    expect(() => parseJob(edit((j) => (j.items[0].ritc = 85076000)))).toThrow('items.0.ritc');
  });

  test('rejects a date that is not dd/mm/yyyy', () => {
    expect(() => parseJob(edit((j) => (j.items[0].reExport.beDate = '2025-09-26')))).toThrow('dd/mm/yyyy');
  });

  test('rejects a Marks & Nos longer than the box', () => {
    expect(() => parseJob(edit((j) => (j.shipment.marksAndNos = 'X'.repeat(301))))).toThrow('marksAndNos');
  });

  test('rejects two items with the same sno', () => {
    expect(() => parseJob(edit((j) => (j.items[1].sno = 1)))).toThrow('share one sno');
  });

  test('rejects two items mapped to the same BE item', () => {
    expect(() => parseJob(edit((j) => (j.items[1].reExport.beItemSlNo = 1)))).toThrow('same BE invoice');
  });

  test('rejects quantity used above the BE quantity', () => {
    expect(() => parseJob(edit((j) => (j.items[0].reExport.beQty = 1000)))).toThrow('above');
  });

  test('rejects quantity used that differs from the exported quantity', () => {
    expect(() => parseJob(edit((j) => (j.items[0].qty = 2000)))).toThrow('must equal qty');
  });
});
