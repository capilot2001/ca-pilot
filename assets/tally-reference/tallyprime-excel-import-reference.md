# TallyPrime — Import Data Using Any Excel File
### Consolidated Reference (Mapping Templates: Masters + Transactions)

**Sources**
- `help.tallysolutions.com/import-data-using-any-excel-file/` — procedures (last updated 3 Feb 2026)
- `help.tallysolutions.com/getting-started-with-importing-data-into-tallyprime/` — field rules, prerequisites, configuration (last updated 25 Mar 2026)

The first page is procedural and defers all field-level detail to the second via hyperlinks. Both are merged below.

---

## 1. Core Concepts

### 1.1 Two import routes

| | Sample (Pre-defined) Excel File | User-Defined Excel File |
|---|---|---|
| Structure | Fixed template supplied by Tally; columns already align to Tally fields | Any layout the business already uses |
| Mapping needed | None — fill and import | Yes — a **Mapping Template** must be created |
| Best for | Quick one-off imports | Recurring imports from an existing/native format |

For the client-upload workflow, the **user-defined route** is the relevant one, since incoming invoice data will be normalised into your own column layout.

### 1.2 What a Mapping Template is

A saved definition that links each **Field (TallyPrime)** to either a **Column Header (Excel)** or a **Column (Excel)** letter. Once saved, the same template is reused on every subsequent import from that worksheet layout.

**Storage location:** `<TallyPrime install folder>\config\excelmaps\`
This is a file-system artifact — relevant if you plan to deploy identical templates across multiple client machines.

Templates are of two scopes:

| Scope | Where saved | Behaviour |
|---|---|---|
| **All Companies** | TallyPrime application folder | Available to every company loaded in that installation |
| **This Company** | Company data folder | Travels with the company data across machines; restrict edit/delete for security |

### 1.3 Excel data layouts the template can handle

- **Multiple Rows** — one transaction spans several rows; party ledger, sales/purchase ledger and tax ledgers all sit in one column across different rows. Enabled via the **Ledger Details from Multiple Rows** option in the template.
- **Multiple / Fixed Columns** — one transaction on a single row; party name and CGST/SGST/IGST each in their own column.

When mapping ledgers in the fixed-column layout, each mapping is designated as:

- **Top Ledger** — Party/Supplier, Bank, Cash
- **Bottom Ledger** — Expenses, Sales, Purchases, and taxes (CGST/SGST/IGST)

### 1.4 Hard limits

- Maximum **702 columns** read from an Excel file.
- Column headers in Sample files must not be renamed (internally mapped).

---

## 2. Prerequisites (must be satisfied before any import)

### 2.1 Dependent masters must already exist

Vouchers will fail or throw exceptions if their referenced masters are absent.

| Data being imported | Must already exist |
|---|---|
| Ledgers | Parent Group |
| Stock Items | Stock Group (falls back to **Primary** if unspecified) |
| Stock Items | Unit of Measurement |
| Compound Units | Both the first and second unit |
| Godown transactions | Godowns + allocation details (if enabled) |
| Payroll / salary vouchers | Pay Heads |
| Any voucher | Required stock items and UoMs |
| Multi-currency | The currency, pre-created in company data |

**Implication for the build:** masters must be imported **before** vouchers. A two-pass pipeline (masters pass → voucher pass) is unavoidable.

### 2.2 Features that must be switched on first

Example — Bill-wise details:
1. `F11` (Features) → **Enable Bill-wise entry** = Yes
2. Party ledger → **Maintain balance bill-by-bill** = Yes

### 2.3 Multi-currency caveat (Release 7.0 onward)

New currency symbols apply to **AED** and **SAR**. Legacy identifiers in an Excel file may cause import failure or display corruption.

- Copy the symbol from the Currency alteration screen, or
- Use `=UNICHAR(8387)` for AED, `=UNICHAR(8385)` for SAR
- The symbols may render as boxes/question marks in Excel — this is expected.

---

## 3. Mandatory & Conditional Field Checklists

### 3.1 Baseline mandatory fields

| Target | Mandatory |
|---|---|
| Accounting Masters (mapping template) | **Name**, **Group Name** |
| Ledgers | Ledger Name, Under Group |
| Vouchers | Date, Voucher Type, Debit/Credit Amount |

### 3.2 Ledger with Bill-wise Details
- Bill Name
- Bill Date
- Bill Amount
- Bill Amount Dr/Cr

### 3.3 Stock Items with BOM
*(BOM must be enabled in TallyPrime first)*
- Name of BOM
- Unit of Manufacture
- BOM Component – Item Name
- BOM Component – Quantity
- BOM Component – Godown/Location
- BOM Component – Type of Item
- BOM Component – Rate (%)

### 3.4 Price List via Stock Item Master
*(Price levels must pre-exist)*

**Mandatory:** Price Level · Price List – Date
**Optional:** Item Quantities – From · Item Quantities – Less Than · Price List Rate · Price List Discount

### 3.5 Payment Vouchers with Bank Allocation
*(Required for correct Bank Reconciliation reporting)*
- Bank Date
- Ledger Amount
- Bank Name

### 3.6 Sales Vouchers — GSTR compliance ⚠️

**This is the critical block for an invoice-processing pipeline.** Omitting these causes invoices to land in GSTR reports as **Uncertain**:

- Buyer/Supplier – Bill To/From
- Buyer/Supplier – Address Type
- Buyer/Supplier – Mailing Name
- Buyer/Supplier – Address
- Buyer/Supplier – Country
- Buyer/Supplier – State
- Buyer/Supplier – GST Registration Type
- Buyer/Supplier – Assessee of Other Territory
- Buyer/Supplier – GSTIN/UIN
- Buyer/Supplier – Is Bill of Entry Available
- Buyer/Supplier – Place of Supply
- Buyer/Supplier – Pincode

Your invoice-extraction layer must capture all twelve, not merely GSTIN and amount.

---

## 4. Workflow A — Import Masters

### Step 1: Create the Mapping Template

*Worked example in the docs: stock item list in worksheet `Sheet1` of `Item List.xlsx`, columns = Item Name, Unit of Measurement, Quantity, Rate, Value.*

1. `Alt+O` (Import) → **Manage** → **Mapping Templates** → **MASTERS** → **Create**
2. Supply the Excel file details, then `Enter`:
   - **File Path** — folder containing the file
   - **File to Import** — select from the list
   - **Worksheet Name** — the sheet to read
   → the **Mapping Template Creation** screen opens
3. Set the save scope: **All Companies** or **This Company**
4. Set structure/row/column details:
   - **Excel Data has column headers** — Yes / No
   - **Row no. for column headers** — e.g. `1`
   - **Import Data from row … to** — e.g. `2` to *(blank = last row with data)*
   - **Import Data from column … to** — e.g. `A` to *(**Last Column** = last populated column)*
5. Map each **Field (TallyPrime)** → **Column Header (Excel)** or **Column (Excel)**
   - **Name** and **Group Name** are mandatory for Accounting Masters
   - Optionally set a **Fixed Value** for a field instead of sourcing it from a column
6. Verify the mapping before saving (explicitly recommended — reduces import failure)
7. `Ctrl+A` to save

### Step 2: Run the Import

1. `Alt+O` (Import) → **Masters** → the **Import Data** screen opens
2. Supply Excel file details (path / file / worksheet)
3. Set **Behaviour of Import if Masters already exists** — controls the impact on existing records
4. **Preview Import Summary** — dry-run view of what will be imported
5. Configure backup, if required
6. Press `I` to import

---

## 5. Workflow B — Import Transactions

*Worked example: sales transactions in worksheet `Sales Bills` of `Sales Transactions Q1.xlsx`, using the **Ledger Details from Multiple Rows** option.*

### Step 1: Create the Mapping Template

1. `Alt+O` → **Manage** → **Mapping Templates** → **TRANSACTIONS** → **Create**
2. Supply Excel file details, then `Enter`
3. Set save scope (All Companies / This Company) and template **Name**
4. Set **Type of Voucher** plus row and column details — identical mechanics to Masters
5. Map **Field (TallyPrime)** → **Column Header (Excel)** / **Column (Excel)**; verify before saving
6. `Ctrl+A` to save

### Step 2: Run the Import

1. `Alt+O` → **Transactions** → **Import Data** screen
2. Supply Excel file details
3. **Preview Import Summary**
4. Configure backup, if required
5. Press `I` to import

> **Note the asymmetry:** the "Behaviour of Import if already exists" option appears in the **Masters** flow only. Voucher duplicate-handling is governed instead by the GUID-based overwrite setting (§7), which applies to XML format.

---

## 6. Managing Templates

### 6.1 Alter

1. `Alt+O` → **Manage** → **Mapping Templates** → **MASTERS** → **Alter**
2. Select the **Mapping Template**, then specify **File Path**, **File to Import**, **Worksheet Name**
3. Edit fields in the **Mapping Template Alteration** screen
4. Accept and save

*Typical use case cited: changing the row number data is read from.*

### 6.2 Delete — single template

1. `Alt+O` → **Manage** → **Mapping Templates** → **Alter**
2. `Alt+D` to delete

### 6.3 Delete — templates saved for **All Companies**

1. `F1` (Help) → **Troubleshooting** → **Delete Mapping Templates Saved for All Companies**
2. From **List of Mapping Templates**, pick the template (docs use *Groups* as the example)
3. Confirm **Yes**

**Bulk:** choose **Delete All** from the same list → confirm **Yes**.

### 6.4 Delete — templates saved for **This Company**

1. `F1` (Help) → **Troubleshooting** → **Delete Mapping Templates Saved for This Company**
2. Select the Company from **List of Companies**
3. Select the template (docs use *Ledger* as the example)
4. Confirm **Yes**

**Bulk:** choose **Delete All** → confirm **Yes**.

---

## 7. Import Configuration Reference

Reached via `Alt+O` → **Import** → **Configuration**.

| Setting | Purpose / Options |
|---|---|
| **Location of Import/Export Files** | Default folder path for import/export files |
| **Behaviour of Import when exceptions exist** | • **Stop Import at First Exception** — halts on first error<br>• **Record Exceptions and Import** — continues, logs to Exceptions Report<br>• **Ignore Exceptions and Import** — imports regardless |
| **Overwriting Vouchers (XML format)** | Same-GUID vouchers overwritten rather than duplicated. Importing into a *different* company overwrites regardless |
| **Removing Invalid Characters (Excel format)** | Strips stray spaces, tabs and special characters. Available Release 3.0.2+ |
| **Import Batch Size** | Records processed per batch |
| **Enable Detailed Log** | Detailed event log for diagnosing failures |

**Recommended setting for an unattended pipeline:** *Record Exceptions and Import*, with **Enable Detailed Log** on — so a single bad invoice doesn't block the batch, and every rejection is traceable. If the data has exceptions, TallyPrime completes the import but flags them in the **Exceptions Report** (Data Exceptions section).

---

## 8. Screen-Field Map (for building a matching UI)

**Mapping Template Creation screen — header block**

| On-screen label | Values |
|---|---|
| Save Mapping Template for | All Companies / This Company |
| Name | free text |
| Type of Master / Type of Voucher | selected from list |
| Excel Data has column headers | Yes / No |
| Row no. for column headers | integer |
| Import Data from row … to | integer … integer *(blank = end)* |
| Import Data from column … to | column letter … column letter / **Last Column** |

**Mapping grid — four columns**

`Field (TallyPrime)` | `Column Header (Excel)` | `Column (Excel)` | `Fixed Value`

Mirroring these exact controls in your web portal means a client's portal-side configuration maps 1:1 onto a Tally template, and template files can be generated rather than hand-built.

---

## 9. Reference Links

| Resource | URL |
|---|---|
| Main article | `help.tallysolutions.com/import-data-using-any-excel-file/` |
| Field rules & configuration | `help.tallysolutions.com/getting-started-with-importing-data-into-tallyprime/` |
| Sample data + ready mapping templates (download) | `help.tallysolutions.com/tally-prime/data-exchange-tally-prime/download-sample-excel-files-with-data-for-import/#sample-data-with-mapping-templates` |
| Data Exceptions / resolutions | `help.tallysolutions.com/data-exceptions-resolutions-in-tallyprime/` |
| Import errors & resolutions | `help.tallysolutions.com/import-data-errors-and-resolutions/` |
| Import Data FAQ | `help.tallysolutions.com/import-data-faq/` |
| Import from JSON or XML | `help.tallysolutions.com/import-data-from-xml-or-json/` |
| TDL capabilities on Excel import | `help.tallysolutions.com/tdl-capabilities-on-import-of-excel-data/` |
| Understanding Tally XML tags | `help.tallysolutions.com/understanding-tally-xml-tags/` |
| Exclude rows in Excel | `help.tallysolutions.com/exclude-rows-in-excel/` |
| Map Nett Amount values | `help.tallysolutions.com/map-nett-amount-values/` |
| Map attendance data | `help.tallysolutions.com/map-attendance-data-from-excel/` |

### Official walkthrough videos

| Topic | Link |
|---|---|
| Overview — import using any Excel file | `youtube.com/watch?v=-GPWXR2goiw` |
| Create mapping template for Masters | `youtu.be/kC8kVLWicGY` |
| Import Masters into TallyPrime | `youtube.com/watch?v=FGzjeBnVtLo` |
| Alter mapping templates | `youtu.be/uurd2euiE3s` |
| Delete templates — All Companies | `youtube.com/watch?v=uB_JzVDFzn4` |
| Delete templates — This Company | `youtube.com/watch?v=ZhhxCK2tX_Q` |

*The transactions-template section has no dedicated video; it is documented as following the Masters mechanics.*

---

## 10. Gap Analysis for the Automation Objective

Flagging this because it materially affects architecture, and it is **not** stated on the help pages:

**Everything documented above is a keyboard-driven desktop workflow.** `Alt+O`, `Ctrl+A`, `I`, `F1` — every step assumes a human at a TallyPrime installation. There is no documented API, CLI switch, or headless mode for Excel-plus-mapping-template import. A portal cannot invoke this path directly.

Practical consequences:

1. **Excel + mapping template is a good fit for the human-in-the-loop stage** — the client or your operator runs the import on their own Tally machine using a template you pre-build and ship into `config\excelmaps\`. Reliable, low-effort, but not "automatic".

2. **For genuine hands-off posting, the XML route is the one to evaluate.** TallyPrime can act as an HTTP server (typically port 9000) accepting XML voucher/master payloads — this is what most third-party Tally integrations use. Worth costing this out before committing to the Excel path, since it changes your portal from "produce a file" to "post to an endpoint". Start with the *Understanding Tally XML Tags* and *Import from JSON or XML* links above.

3. **Either way, the field checklists in §3 are the real specification** for your invoice-extraction layer — especially §3.6. Getting GSTIN and amounts is not sufficient; twelve buyer/supplier attributes are needed to keep sales invoices out of GSTR "Uncertain".

4. **Sequencing is fixed:** masters before vouchers, always. Your pipeline needs a reconciliation step that detects unknown ledgers/stock items in an incoming invoice and creates them first.

5. **Archival requirement is orthogonal** to Tally entirely — storing the source invoice PDF/image alongside the generated Excel is your own storage layer's job, and should be keyed on something Tally also holds (voucher number + date + party) so records can be traced back after import.
