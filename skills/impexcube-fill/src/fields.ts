// Field ids on export.impexcube.in, found by inspecting a real export job.
// If ImpexCube renames a control, this is the only file to fix.

const PRODUCT = 'ContentPlaceHolder1_tbProduct_TabPanel1_';
const REEXPORT = 'ContentPlaceHolder1_tbProduct_TabPanel6_';
const SHIPMENT = 'ContentPlaceHolder1_Shipment_TabPanelExch_';
const JOB = 'ContentPlaceHolder1_tbJobCreation_TabPanel5_';

export const job = {
  nfeiCategory: `${JOB}ddlNFEICategory`,
  exporterRefNo: `${JOB}txtExporterRefNo`,
  save: `${JOB}btnUpdate`,
};

export const shipment = {
  marksAndNos: `${SHIPMENT}txtRemarks`,
  save: `${SHIPMENT}btnUpdate`,
};

export const product = {
  /** a fresh session shows no product grid until an invoice is chosen here */
  invoice: 'ContentPlaceHolder1_ddlInvNo',
  gridElement: `${PRODUCT}gvProductExp`,
  grid: 'ctl00$ContentPlaceHolder1$tbProduct$TabPanel1$gvProductExp',
  sno: `${PRODUCT}txtSNo`,
  description: `${PRODUCT}txtDesc`,
  ritc: `${PRODUCT}txtRitccode`,
  type: `${PRODUCT}ddltype`,
  qty: `${PRODUCT}txtQuan`,
  igstStatus: `${PRODUCT}ddlpaymntstatus`,
  save: `${PRODUCT}btnUpdate`,
};

export const reExport = {
  grid: 'ctl00$ContentPlaceHolder1$tbProduct$TabPanel6$gvrexport',
  tabHeader: '__tab_ContentPlaceHolder1_tbProduct_TabPanel6',
  rowDeleteButtonPrefix: `${REEXPORT}gvrexport_btnrexpDelete_`,
  beSite: `${REEXPORT}txtBESite`,
  beNo: `${REEXPORT}txtbenumber1`,
  beDate: `${REEXPORT}txtbenumdate`,
  beInvSlNo: `${REEXPORT}txtInvNoBE`,
  beItemSlNo: `${REEXPORT}txtBEItem`,
  qtyUtilised: `${REEXPORT}txtquantityimport3`,
  beItemDesc: `${REEXPORT}txtbeitemdesc`,
  beQty: `${REEXPORT}txtBEQty`,
  beAssdValue: `${REEXPORT}txtassessibleval1`,
  dutyPaid: `${REEXPORT}txttotaldutypaid`,
  otherParam: `${REEXPORT}txtothIdenParam1`,
  save: `${REEXPORT}btnrexpUpdate`,
};

/** The only buttons the script may ever click. */
export const SAVE_BUTTONS: readonly string[] = [job.save, shipment.save, product.save, reExport.save];

export type StepName = 'job' | 'shipment' | 'items';

export interface Step {
  name: StepName;
  label: string;
  path: (jobNo: string) => string;
  /** an element that exists once the form is usable */
  ready: string;
}

/** The pages a job touches, in order. Job Details comes first: it tells ImpexCube which job the others show. */
export const STEPS: readonly Step[] = [
  {
    name: 'job',
    label: 'Job Details',
    path: (jobNo) => `frmExportJobCreation.aspx?JobNo=${encodeURIComponent(jobNo)}&Mode=Edit`,
    ready: job.nfeiCategory,
  },
  {
    name: 'shipment',
    label: 'Shipment',
    path: () => 'efrmShipment.aspx?Mode=Export',
    ready: shipment.marksAndNos,
  },
  {
    name: 'items',
    label: 'Product and Re-Export',
    path: () => 'frmEProductMainPage.aspx?Mode=Invoice',
    ready: product.description,
  },
];
