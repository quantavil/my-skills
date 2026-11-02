# eSANCHIT IRN workflow

Never send email in this workflow. Read [portal steps](portal-steps.md) and [Gmail operations](gmail.md). Do not invent selectors, codes, IDs or results.

1. Identify the target thread and newest external message containing PDFs; save its sender, cc, message ID and attachment names. Ask the user to label each PDF with its document type; do not infer uncertain labels. Use a new private folder outside the repo for downloads and working files.
2. Sign the PDFs using the available signing tool after a dry run and verify each signed output. The user enters the PIN directly in the terminal. Confirm file identity, size and document types. Do not upload if validation fails.
3. Use the shared [ICEGATE login module](icegate-login.md). On first use, perform a read-only portal walkthrough and record observed selectors and document types in the portal reference before any upload. Do not expose credentials or session data.
4. Search confirmations and portal records for prior submissions. A filename match alone is not proof of identical content or a safe basis for either skipping or re-uploading; reconcile ambiguity with the user. Submit each intended batch once. If the outcome is uncertain, stop and reconcile; never retry automatically.
5. Poll for the confirmation, reconcile every uploaded file exactly once with its IRN, DRN and selected type. Stop on missing, extra, duplicate or ambiguous matches. Create a reply draft only after successful reconciliation; leave it unsent.
