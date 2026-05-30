// Typed client for the FastAPI backend. Dev requests go through the Vite /api proxy.
import type {
  Decision,
  Graph,
  Notification,
  RoutingDecision,
  ScoredRecord,
  TransactionsResponse,
} from "./types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export interface TransactionFilters {
  card_id?: string;
  merchant?: string;
  category?: string;
  reason?: string;
  channel?: string;
  min_score?: number;
  max_score?: number;
  min_amount?: number;
  max_amount?: number;
  date_from?: string;
  date_to?: string;
  status?: string;
  action?: string;
  sort?: string;
}

export async function fetchTransactions(f: TransactionFilters = {}): Promise<ScoredRecord[]> {
  const qs = new URLSearchParams(
    Object.entries(f)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)])
  ).toString();
  const res = await get<TransactionsResponse>(`/transactions${qs ? `?${qs}` : ""}`);
  return res.results;
}

export const fetchTransaction = (id: string) => get<ScoredRecord>(`/transaction/${id}`);
export const fetchGraph = () => get<Graph>("/graph");

export interface SummaryResponse {
  transaction_id: string;
  summary: string | null;
  enabled: boolean;
}
export const fetchSummary = (id: string) => get<SummaryResponse>(`/transaction/${id}/summary`);

export const fetchNotifications = () =>
  get<{ count: number; results: Notification[] }>("/notifications");

export interface IngestResponse {
  record: ScoredRecord;
  decision: RoutingDecision;
  notification: Notification | null;
}

export async function createTransaction(body: Record<string, unknown>): Promise<IngestResponse> {
  const res = await fetch(`${BASE}/transactions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export interface ReviewResponse {
  transaction_id: string;
  review_status: string;
  suppressed: string[];
  new_flag_count: number;
  audit_id: string;
}

export async function review(id: string, decision: Decision, reviewer: string = "system"): Promise<ReviewResponse> {
  const res = await fetch(`${BASE}/review/${id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, reviewer }),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export interface UndoResponse {
  undone: string | null;
  restored_status?: string;
  new_flag_count?: number;
}

export async function postUndo(): Promise<UndoResponse> {
  const res = await fetch(`${BASE}/undo`, { method: "POST" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export interface ThresholdResponse {
  threshold: number;
  old_flag_count: number;
  new_flag_count: number;
}

export async function postThreshold(fpCost: number, fnCost: number): Promise<ThresholdResponse> {
  const res = await fetch(`${BASE}/threshold`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fp_cost: fpCost, fn_cost: fnCost }),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const fetchAudit = () => get<{ entries: any[] }>("/audit");
