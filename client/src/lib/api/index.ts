import { apiDownload, apiFetch, apiPost, apiUpload } from "./client";
import type {
  Client,
  ClientList,
  CompanyConfig,
  ExportKind,
  Invoice,
  ReconSummary,
} from "./types";

export * from "./types";
export { ApiError } from "./errors";

// ——— active company / config ————————————————————————————————————————
export const getConfig = () => apiFetch<CompanyConfig>("/api/config");
export const saveConfig = (c: CompanyConfig) =>
  apiPost<CompanyConfig>("/api/config", c);

// ——— stored clients (the one persisted surface) ——————————————————————
export const listClients = (q = "") =>
  apiFetch<ClientList>(`/api/clients?q=${encodeURIComponent(q)}`);
export const createClient = (c: CompanyConfig, activate = true) =>
  apiPost<Client>(`/api/clients?activate=${activate}`, c);
export const updateClient = (id: number, c: CompanyConfig) =>
  apiFetch<Client>(`/api/clients/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(c),
  });
export const activateClient = (id: number) =>
  apiPost<Client>(`/api/clients/${id}/activate`, {});
export const deleteClient = (id: number) =>
  apiFetch<{ deleted: number; active_id: number | null }>(
    `/api/clients/${id}`,
    { method: "DELETE" }
  );

// ——— extraction / import / recompute / reconcile ————————————————————
export const extract = (files: File[]) =>
  apiUpload<Invoice[]>("/api/extract", files);
export const importGstr2a = (files: File[]) =>
  apiUpload<Invoice[]>("/api/import/gstr2a", files);
export const recompute = (invoices: Invoice[]) =>
  apiPost<Invoice[]>("/api/recompute", { invoices });
export const reconcile = (invoices: Invoice[]) =>
  apiPost<ReconSummary>("/api/reconcile", { invoices });

// ——— exports ————————————————————————————————————————————————————————
export async function downloadExport(kind: ExportKind, invoices: Invoice[]) {
  const { blob, filename } = await apiDownload(`/api/export/${kind}`, {
    invoices,
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
