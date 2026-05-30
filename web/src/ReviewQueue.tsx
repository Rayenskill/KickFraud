// One-transaction-at-a-time triage, keyboard-driven, with undo.
// SCAFFOLD: fetches contract-shaped stub data so the UI builds in parallel with the detector.
// TODO (H2-H10): keyboard nav (j/k, a/d/e), detail pane, undo, in-session feedback loop.
import { useEffect, useState } from "react";
import { fetchTransactions } from "./api";
import type { ScoredRecord } from "./types";

export function ReviewQueue() {
  const [records, setRecords] = useState<ScoredRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTransactions().then(setRecords).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p>API not running yet: {error}</p>;

  return (
    <ul>
      {records.map((r) => (
        <li key={r.transaction_id}>
          <strong>[{r.fraud_score.toFixed(2)}]</strong> {r.card_id} — {r.merchant} ($
          {r.amount}) — {r.label}
          {r.reasons.length > 0 && <em> · {r.reasons[0].text}</em>}
        </li>
      ))}
    </ul>
  );
}
