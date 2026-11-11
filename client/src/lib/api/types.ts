/**
 * TypeScript mirror of the backend contract (shared.models + the API schemas).
 * Kept in sync by hand for now; can be generated from the backend OpenAPI later.
 */

export interface LineItem {
  description: string;
  hsn_sac: string;
  quantity: number | null;
  unit: string;
  rate: number | null;
  disc_pct: number | null;
  taxable_value: number | null;
  gst_rate: number | null;
  amount: number | null;
  ledger: string;
}

export interface Assumption {
  field: string;
  value: string;
  reason: string;
}

export type Severity = "error" | "warning" | "info";

export interface Exception_ {
  code: string;
  severity: Severity;
  message: string;
}

export interface TaxBreakup {
  cgst: number;
  sgst: number;
  igst: number;
  cess: number;
  round_off: number;
}

export interface JournalLine {
  ledger: string;
  debit: number;
  credit: number;
}

export interface Invoice {
  source_file: string;
  ocr_engine: string;
  raw_text: string;
  source: "invoice" | "gstr2a";
  direction: "purchase" | "sale" | "unknown";
  nature_of_transaction: "intra-state" | "inter-state" | "unknown";
  accounting_classification: string;
  entry_mode: "item" | "accounting";
  party_name: string;
  party_gstin: string;
  party_state_code: string;
  party_state: string;
  party_address: string;
  party_pincode: string;
  party_registration_type: string;
  invoice_number: string;
  invoice_date: string;
  invoice_date_display: string;
  place_of_supply: string;
  place_of_supply_code: string;
  items: LineItem[];
  taxable_total: number;
  tax: TaxBreakup;
  printed_tax: TaxBreakup | null;
  invoice_total: number;
  dominant_gst_rate: number | null;
  journal: JournalLine[];
  itc_eligible: boolean | null;
  itc_remarks: string;
  assumptions: Assumption[];
  exceptions: Exception_[];
}

export interface CompanyConfig {
  id?: number;
  name: string;
  gstin: string;
  state_code: string;
  pan: string;
  registration_type: string;
  address: string;
  pincode: string;
  stock_enabled: boolean;
  state?: string;
  country?: string;
  gstin_valid?: boolean;
  gstin_reason?: string;
  updated_at?: string;
}

export type Client = CompanyConfig & { id: number };

export interface ClientList {
  clients: Client[];
  active_id: number | null;
}

export type ReconStatus =
  | "matched"
  | "only_in_2a"
  | "only_in_books"
  | "value_mismatch";

export interface ReconLine {
  status: ReconStatus;
  party_name: string;
  party_gstin: string;
  invoice_number: string;
  invoice_date: string;
  books_taxable: number;
  books_tax: number;
  gstr2a_taxable: number;
  gstr2a_tax: number;
  taxable_diff: number;
  tax_diff: number;
  diffs: string[];
  remark: string;
}

export interface ReconSummary {
  books_count: number;
  gstr2a_count: number;
  matched: number;
  only_in_2a: number;
  only_in_books: number;
  value_mismatch: number;
  books_tax_total: number;
  gstr2a_tax_total: number;
  itc_at_risk: number;
  lines: ReconLine[];
}

export type ExportKind =
  | "masters-xlsx"
  | "vouchers-xlsx"
  | "masters-xml"
  | "vouchers-xml"
  | "recon-xlsx"
  | "recon-pdf";
