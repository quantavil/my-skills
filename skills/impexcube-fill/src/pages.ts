import { el, maybeEl, RunError, read, readFresh, requireJob } from './dom';
import * as f from './fields';
import { openReExportTab, selectRow, setField } from './postback';
import { type Context, differences, reconcile, type Spec, same } from './reconcile';
import type { Item, Job, ReExportRow } from './schema';

export type Sync = (job: Job, ctx: Context) => Promise<void>;

const text = (label: string, id: string, want: string): Spec => ({ label, id, want, kind: 'text' });
const num = (label: string, id: string, want: number): Spec => ({
  label,
  id,
  want: String(want),
  kind: 'num',
});

/** After saving a plain form: fetch the page again and report what the server still shows wrong. */
const confirmFresh = (specs: readonly Spec[]) => async (): Promise<Spec[]> => {
  const fresh = await readFresh(specs.map((s) => s.id));
  return specs.filter((s) => !same(s.kind, fresh[s.id] ?? '', s.want));
};

async function syncForm(tag: string, specs: Spec[], saveId: string, ctx: Context): Promise<void> {
  if (specs.length === 0) return ctx.log(`${tag}: nothing in the file`);
  await reconcile(tag, specs, saveId, ctx, confirmFresh(specs));
}

export const syncJobDetails: Sync = (job, ctx) => {
  requireJob(job.jobNo);
  const specs: Spec[] = [];
  if (job.jobDetails?.nfeiCategory !== undefined)
    specs.push(text('NFEI category', f.job.nfeiCategory, job.jobDetails.nfeiCategory));
  if (job.jobDetails?.exporterRefNo !== undefined)
    specs.push(text('exporter ref', f.job.exporterRefNo, job.jobDetails.exporterRefNo));
  return syncForm('Job details', specs, f.job.save, ctx);
};

export const syncShipment: Sync = (job, ctx) => {
  requireJob(job.jobNo);
  const marks = job.shipment?.marksAndNos;
  const specs = marks === undefined ? [] : [text('Marks & Nos', f.shipment.marksAndNos, marks)];
  return syncForm('Shipment', specs, f.shipment.save, ctx);
};

// Type is a dropdown that posts back and redraws the form, so it goes first.
const productSpecs = (item: Item): Spec[] => [
  text('type', f.product.type, item.type),
  text('RITC', f.product.ritc, item.ritc),
  num('qty', f.product.qty, item.qty),
  text('IGST status', f.product.igstStatus, item.igstStatus),
  text('description', f.product.description, item.description),
];

const reExportSpecs = (row: ReExportRow): Spec[] => [
  text('BE site', f.reExport.beSite, row.beSite),
  text('BE no', f.reExport.beNo, row.beNo),
  text('BE date', f.reExport.beDate, row.beDate),
  num('BE inv sl no', f.reExport.beInvSlNo, row.beInvSlNo),
  num('BE item sl no', f.reExport.beItemSlNo, row.beItemSlNo),
  num('qty utilised', f.reExport.qtyUtilised, row.qtyUtilised),
  text('BE item desc', f.reExport.beItemDesc, row.beItemDesc),
  num('BE qty', f.reExport.beQty, row.beQty),
  num('BE assessable value', f.reExport.beAssdValue, row.beAssdValue),
  num('duty paid', f.reExport.dutyPaid, row.dutyPaid),
  text('other parameter', f.reExport.otherParam, row.otherParam),
];

/** Select an item's grid row and prove the form shows that item (never trust the row position). */
async function openItem(item: Item): Promise<void> {
  await selectRow(f.product.grid, item.sno - 1);
  const shown = Number(read(f.product.sno));
  if (shown !== item.sno) {
    throw new RunError(
      `Grid row ${item.sno} shows S.No ${shown || 'blank'}, not ${item.sno}. Stopped; check the grid order.`,
    );
  }
}

const reExportRows = () => document.querySelectorAll(`[id^="${f.reExport.rowDeleteButtonPrefix}"]`).length;

async function syncProduct(item: Item, ctx: Context): Promise<void> {
  const specs = productSpecs(item);
  await reconcile(`Item ${item.sno}`, specs, f.product.save, ctx, async () => {
    await openItem(item);
    return differences(specs);
  });
}

async function syncReExport(item: Item, ctx: Context): Promise<void> {
  if (!item.reExport) return;
  const tag = `Item ${item.sno} re-export`;
  await openReExportTab();
  const rows = reExportRows();
  if (rows > 1) {
    ctx.log(`${tag}: ${rows} rows, expected 1. Delete the extras in ImpexCube first`, true);
    if (ctx.apply) throw new RunError(`${tag}: duplicate rows, nothing was changed for this item`);
    return;
  }
  if (rows === 0) ctx.log(`${tag}: no row yet`, true);
  else await selectRow(f.reExport.grid, 0);
  const specs = reExportSpecs(item.reExport);
  await reconcile(tag, specs, f.reExport.save, ctx, async () => {
    await openItem(item);
    await openReExportTab();
    const after = reExportRows();
    if (after !== 1) throw new RunError(`${tag}: ${after} rows after saving, expected 1`);
    await selectRow(f.reExport.grid, 0);
    return differences(specs);
  });
}

/** A fresh session shows no product grid until the invoice is chosen. Choosing it changes no data. */
async function ensureInvoice(job: Job): Promise<void> {
  if (maybeEl(f.product.gridElement)) return;
  const select = el<HTMLSelectElement>(f.product.invoice);
  const options = [...select.options].map((o) => o.value).filter(Boolean);
  const wanted = job.invoiceNo ?? (options.length === 1 ? options[0] : undefined);
  if (!wanted)
    throw new RunError(`The page lists ${options.length} invoices; add "invoiceNo" to the job file.`);
  await setField(f.product.invoice, wanted);
  if (!maybeEl(f.product.gridElement))
    throw new RunError(`Choosing invoice ${wanted} did not show the product grid.`);
}

export const syncItems: Sync = async (job, ctx) => {
  requireJob(job.jobNo);
  el(f.product.description);
  await ensureInvoice(job);
  for (const item of [...job.items].sort((a, b) => a.sno - b.sno)) {
    await openItem(item);
    await syncProduct(item, ctx);
    await syncReExport(item, ctx);
  }
  ctx.log('Items: done');
};
