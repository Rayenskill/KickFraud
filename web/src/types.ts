// Frozen scored-record contract (TypeScript side).
// Mirrors contract/scored_record.schema.json, docs/JSON_CONTRACT.md, detector/schema.py.
// FROZEN (H0-H2). Changes require a sync with the detector owner.

export type Channel = "online" | "in_person";
export type Label = "fraud" | "clear";
export type ReviewStatus = "pending" | "approved" | "dismissed" | "escalated";
export type Decision = "approve" | "dismiss" | "escalate";
export type NodeType = "card" | "merchant";
export type EdgeType = "co_burst" | "shared_ip" | "shared_device";

export interface Reason {
  signal: string;
  weight: number;
  text: string;
}

export interface ScoredRecord {
  transaction_id: string; // "tx_001003"
  card_id: string;
  timestamp: string;
  amount: number;
  merchant: string;
  merchant_country: string;
  category: string;
  channel: Channel;
  device_id: string | null;
  ip_address: string | null;
  fraud_score: number; // 0..1
  label: Label;
  reasons: Reason[]; // ranked, non-empty when label === "fraud"
  card_median: number;
  review_status: ReviewStatus;
}

export interface TransactionsResponse {
  count: number;
  results: ScoredRecord[];
}

export interface GraphNode {
  id: string;
  type: NodeType;
  flag_count?: number;
  suspicious?: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: EdgeType;
  weight?: number;
  ip?: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
