# impexcube-fill: development reference

Checks and fixes an ImpexCube export job against one JSON file. Bun and TypeScript, one browser bundle, no UI.
It **saves only**: the four Update buttons are the only things it can click. Login, Approve, SB File and Submit stay with the user.

How Claude runs it in the browser pane is in `SKILL.md`. This file is the reference for people working on the code.

## What it covers

| Step | Page | Fields |
| --- | --- | --- |
| `job` | Job Details | NFEI category, exporter reference |
| `shipment` | Shipment | Marks & Nos |
| `items` | Product + Re-Export | per item: Type, RITC, quantity, IGST status, description, and the Re-Export row (BE site, number, date, item serials, quantity used, description, quantity, assessable value, duty paid, container) |

Not covered: creating the job, Invoice, Container, Manufacturer, E-Sanchit uploads, the Shipment container count (it resets to 0 after some reloads, so check it by eye).

## Safety guarantees

- Only the four known Update buttons can be clicked (exact ids in `src/fields.ts`), and only if the label is "Update".
- The job number on every page must match the file. A page with no visible job number is refused.
- Each grid row is checked against the item's S.No before anything is edited.
- Every save is confirmed: Product by reselecting the row, Job Details and Shipment by fetching the page again.
- A duplicate Re-Export row, a logged-out session, a full-page reload or a failed confirmation stops the run.
- One run at a time. The job file is validated strictly: unknown keys, wrong types, bad dates and inconsistent totals are rejected.

## What a pass means

A pass means only that the fields in the job file match. Every run ends with a line such as

`Result: 0 differences in 19 compared fields. 112 other fields hold values that this tool does not check.`

Each page also prints `compared N of M fields; K others hold values and were not compared`; `audit` lists those K fields with their values. A control that is on the page but in neither the job file nor `known.json` is reported as `NEW, not in known.json: <id>` and counts as a difference. That is how a field ImpexCube adds later, or one we never modelled, shows up.

`known.json` holds the control ids seen on each page (grid rows, hidden state and buttons are ignored). Change it by hand and review it as a diff. UpdatePanels draw different controls for different Types, so the first job of a new shape may report a few controls that are not really new.

## Command line

For when the browser pane is not available. It drives a dedicated Chromium over CDP; the Chromium has its own profile, so the login is remembered there, and its debugging port listens on `127.0.0.1:9222` only.

```bash
bun install
bun run browser                              # start the Chromium; log in to ImpexCube in it yourself
bun run fill <job.json>                      # check only
bun run fill <job.json> --apply              # fix, save and confirm
bun run fill <job.json> --only items         # job | shipment | items
bun run fill <job.json> --audit              # also list every field it did not compare
```

Exit code: 0 matches or fixed, 1 differences found, 2 error or logged out.

Other scripts: `bun run build` (writes the bundle to `~/.cache/impexcube-fill/`, outside this folder so building never changes the skill's hash), `bun run check` (typecheck, Biome, tests), `bun run payload [known]` (prints the statement that stores the bundle or `known.json` in the browser pane).

## Job file

Example: `tests/fixtures/sample-job.json` (fake data). Real job files hold customer data: keep them outside this repository.

- `type` is the ImpexCube Type code: `99` NFEI, `00` foreign exchange, `98` Indian currency.
- `nfeiCategory` is the dropdown value (`8` Others).
- `invoiceNo` is the entry in the Invoice No dropdown. A fresh login shows no product grid until an invoice is chosen; the code chooses it, using this value or the only invoice listed.
- Dates are `dd/mm/yyyy`, RITC is 8 digits as text, and `reExport.qtyUtilised` must equal `qty`.

## Adding a field

1. Run with `--audit` and find the field.
2. Add its id to `src/fields.ts`.
3. Add its key to `src/schema.ts`.
4. Add a spec for it in `src/pages.ts`.
5. Add a test, then `bun run check`.
6. Build, store the new bundle in the pane (`bun run payload`), and run a check.

## Layout

| File | Job |
| --- | --- |
| `src/fields.ts` | every ImpexCube id, the step list, the save-button allowlist |
| `src/schema.ts` | job file schema (Valibot) |
| `src/dom.ts` | element lookup, job-number guard, fresh read from the server |
| `src/postback.ts` | WebForms engine: wait for idle, run an action, wait for its postback, set a field, select a row, save |
| `src/reconcile.ts` | compare, fix, confirm |
| `src/pages.ts` | what to check on each page |
| `src/coverage.ts` | which controls a run did not compare, and which are new |
| `src/run.ts` | `runAll` (hidden frames, progress, timeouts) and `runStep` |
| `known.json` | control ids already seen on each page |
| `cli/`, `scripts/` | Chromium launcher and runner, build, payload |
| `tests/` | `bun test` with happy-dom and a fake PageRequestManager |

## WebForms rules the code follows

1. Setting `.value` does nothing on the server unless a `change` event fires.
2. Dropdowns such as Type post back and redraw the form: set them first, wait, re-read before saving.
3. A postback replaces the elements: look them up again by id.
4. Select the grid row first, or Update saves nothing.
5. Wait until idle before acting, and wait for the postback that the action itself started.
