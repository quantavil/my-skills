# impexcube-fill

Checks and fixes an ImpexCube export job against one JSON file. Bun and TypeScript, one small bundle, no UI.
It **saves only**: the four Update buttons are the only things it can click. Login, Approve, SB File and Submit stay with the user.

## What it covers

| Step | Page | Fields |
| --- | --- | --- |
| `job` | Job Details | NFEI category, exporter reference |
| `shipment` | Shipment | Marks & Nos |
| `items` | Product + Re-Export | per item: Type, RITC, quantity, IGST status, description, and the Re-Export row (BE site, number, date, item serials, quantity used, description, quantity, assessable value, duty paid, container) |

Not covered: creating the job, Invoice, Container, Manufacturer, E-Sanchit uploads, the Shipment container count.

## Safety rules in the code

- Only the four known Update buttons can be clicked (exact ids in `src/fields.ts`), and only if the label is "Update".
- The job number on every page must match the file. A page with no visible job number is refused.
- Each grid row is checked against the item's S.No before anything is edited.
- Every save is confirmed: Product by reselecting the row, Job Details and Shipment by fetching the page again.
- A duplicate Re-Export row, a logged-out session, a full-page reload or a failed confirmation stops the run.
- Only one run at a time; the job file is validated strictly (unknown keys, wrong types, bad dates and totals are rejected).

## Run it

```bash
bun install
bun run build            # ~/.cache/impexcube-fill/impexcube-fill.js and VERSION (outside the skill folder)
bun run check            # typecheck + Biome + tests
```

**1. Claude's browser pane (default).** Store `~/.cache/impexcube-fill/impexcube-fill.js` once in the pane (`localStorage.ifBundle`), store the job (`localStorage.ifJob`), then:

```js
(0, eval)(localStorage.ifBundle);
impexFill.runAll(localStorage.ifJob, /* apply */ false, localStorage.ifBundle,
  { known: JSON.parse(localStorage.ifKnown) /*, only: 'job'|'shipment'|'items', audit: true */ });
// about 40 s later:
JSON.stringify(window.__impexProgress)   // {version, lines, differences, compared, notCompared, unknown, ok, done}
```

`impexFill.version` must equal the `VERSION` file next to the bundle, otherwise store the bundle again. `ifKnown` is `known.json` (it changes rarely, so it is stored apart from the code).

**2. Separate Chromium (fallback).** It uses its own profile, so the login is remembered there.

```bash
bun run browser                                   # start it; log in to ImpexCube yourself
bun run fill <jobs folder>/EXP-2627-123.json               # check only
bun run fill <jobs folder>/EXP-2627-123.json --apply       # fix and save
bun run fill <jobs folder>/EXP-2627-123.json --only items  # job | shipment | items
bun run fill <jobs folder>/EXP-2627-123.json --audit       # also list every field it did not compare
```

Exit code: 0 matches or fixed, 1 differences found, 2 error or logged out. The debugging port is `127.0.0.1:9222` only. Both routes run the same `runAll`.

## What a pass means

A pass means only that the fields in the job file match. Every run ends with a line such as

`Result: 0 differences in 19 compared fields. 112 other fields hold values that this tool does not check.`

and each page prints `compared N of M fields; K others hold values and were not compared`. `--audit` (or `audit: true`) lists those K fields with their values. A control that is on the page but in neither the job file nor `known.json` is reported as `NEW, not in known.json: <id>` and counts as a difference (exit code 1). That is how a field ImpexCube adds later, or one we never modelled, shows up.

`known.json` holds the control ids seen on each page (grid rows, hidden state and buttons are ignored). Change it by hand and review it as a diff; do not paste ids in blindly. UpdatePanels draw different controls for different Types, so the first job of a new shape may report a few controls that are not really new.

## Adding a field

1. Run with `--audit` and find the field.
2. Add its id to `src/fields.ts`.
3. Add its key to `src/schema.ts`.
4. Add a spec for it in `src/pages.ts`.
5. Add a test, then `bun run check`.
6. `bun run build`, store the new bundle, and run a check.

## Layout

| File | Job |
| --- | --- |
| `src/fields.ts` | every ImpexCube id, the step list, the save-button allowlist |
| `src/schema.ts` | job file schema (Valibot) |
| `src/coverage.ts` | which controls a run did not compare, and which are new |
| `known.json` | control ids already seen on each page |
| `src/dom.ts` | element lookup, job-number guard, fresh read from the server |
| `src/postback.ts` | WebForms engine: wait for idle, run an action, wait for its postback, set field, select row, save |
| `src/reconcile.ts` | compare, fix, confirm |
| `src/pages.ts` | what to check on each page |
| `src/run.ts` | `runAll` (hidden frames, progress, timeouts) and `runStep` |
| `cli/` | Chromium launcher and the thin runner |
| `tests/` | `bun test` with happy-dom and a fake PageRequestManager |

## WebForms rules the code follows

1. Setting `.value` does nothing on the server unless a `change` event fires.
2. Dropdowns such as Type post back and redraw the form: set them first, wait, re-read before saving.
3. A postback replaces the elements; look them up again by id.
4. Select the grid row first or Update saves nothing.
5. Wait until idle before acting, and wait for the postback that the action itself started.

## Job file

See `tests/fixtures/sample-job.json` (fake data). Real job files hold customer data: keep them outside this repository. `type` is the ImpexCube Type code (`99` NFEI, `00` foreign exchange, `98` Indian currency), `nfeiCategory` the dropdown value (`8` Others). `invoiceNo` is the entry in ImpexCube's Invoice No dropdown; a fresh login shows no product grid until it is chosen, and the code chooses it (needed only if the job has several invoices). Dates are `dd/mm/yyyy`, RITC is 8 digits as text, `reExport.qtyUtilised` must equal `qty`.
