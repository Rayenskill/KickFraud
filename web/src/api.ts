// Typed client for the FastAPI backend. Dev requests go through the Vite /api proxy.
import type { Decision, Graph, ScoredRecord, TransactionsResponse } from "./types";

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
  min_score?: number;
  max_score?: number;
  status?: string;
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

// TODO (step 2/3): server returns 501 until implemented.
export async function review(id: string, decision: Decision, reviewer: string): Promise<void> {
  await fetch(`${BASE}/review/${id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, reviewer }),
  });
}
