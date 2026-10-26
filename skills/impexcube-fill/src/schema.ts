import * as v from 'valibot';

const text = v.pipe(v.string(), v.minLength(1));
const whole = v.pipe(v.number(), v.integer(), v.minValue(1));
const amount = v.pipe(v.number(), v.minValue(0));

const reExportSchema = v.strictObject({
  beSite: text,
  beNo: v.pipe(v.string(), v.regex(/^\d+$/, 'must be digits only')),
  beDate: v.pipe(v.string(), v.regex(/^\d{2}\/\d{2}\/\d{4}$/, 'must look like dd/mm/yyyy')),
  beInvSlNo: whole,
  beItemSlNo: whole,
  qtyUtilised: v.pipe(v.number(), v.minValue(0.001)),
  beItemDesc: text,
  beQty: v.pipe(v.number(), v.minValue(0.001)),
  beAssdValue: amount,
  dutyPaid: amount,
  otherParam: v.string(),
});

const itemSchema = v.pipe(
  v.strictObject({
    sno: whole,
    description: text,
    ritc: v.pipe(v.string(), v.regex(/^\d{8}$/, 'must be 8 digits, as text')),
    qty: v.pipe(v.number(), v.minValue(0.001)),
    /** ImpexCube Type code: "99" NFEI, "00" foreign exchange, "98" Indian currency */
    type: v.pipe(v.string(), v.regex(/^\d{2}$/, 'must be a 2-digit code, as text')),
    igstStatus: v.pipe(v.string(), v.regex(/^[A-Z]{1,4}$/, 'must be a code such as NA')),
    reExport: v.optional(reExportSchema),
  }),
  v.check(
    (item) => !item.reExport || item.reExport.qtyUtilised <= item.reExport.beQty,
    'reExport.qtyUtilised is above reExport.beQty',
  ),
  v.check(
    (item) => !item.reExport || item.reExport.qtyUtilised === item.qty,
    'reExport.qtyUtilised must equal qty',
  ),
);

const jobSchema = v.pipe(
  v.strictObject({
    jobNo: v.pipe(v.string(), v.regex(/^EXP-\d{4}-\d+$/, 'must look like EXP-2627-123')),
    jobDetails: v.optional(
      v.strictObject({ nfeiCategory: v.optional(v.string()), exporterRefNo: v.optional(v.string()) }),
    ),
    // ImpexCube's Marks & Nos box holds 300 characters
    shipment: v.optional(v.strictObject({ marksAndNos: v.pipe(text, v.maxLength(300)) })),
    /** as listed in ImpexCube's Invoice No dropdown; needed only when the job has several invoices */
    invoiceNo: v.optional(text),
    items: v.pipe(v.array(itemSchema), v.minLength(1)),
  }),
  v.check((job) => new Set(job.items.map((i) => i.sno)).size === job.items.length, 'two items share one sno'),
  v.check((job) => {
    const keys = job.items.flatMap((i) =>
      i.reExport ? [`${i.reExport.beInvSlNo}/${i.reExport.beItemSlNo}`] : [],
    );
    return new Set(keys).size === keys.length;
  }, 'two items point at the same BE invoice and item serial'),
);

export type Job = v.InferOutput<typeof jobSchema>;
export type Item = Job['items'][number];
export type ReExportRow = v.InferOutput<typeof reExportSchema>;

/** Parses a job file. Throws one readable message listing what is wrong. */
export function parseJob(source: string): Job {
  let data: unknown;
  try {
    data = JSON.parse(source);
  } catch (error) {
    throw new Error(`Job file is not valid JSON (${(error as Error).message})`);
  }
  const result = v.safeParse(jobSchema, data);
  if (result.success) return result.output;
  const problems = result.issues
    .slice(0, 6)
    .map((issue) => `${v.getDotPath(issue) ?? 'job'}: ${issue.message}`);
  throw new Error(`Job file problems:\n  ${problems.join('\n  ')}`);
}
