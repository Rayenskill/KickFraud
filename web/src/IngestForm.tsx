import { useState } from "react";
import { createTransaction, IngestResponse } from "./api";

interface IngestFormProps {
  onIngested: () => void;
  showToast: (msg: string) => void;
}

// Presets make the decision tree easy to demo. The "ring" preset lands a >$200 QuickPay
// charge inside the May-17 coordinated burst window, so it completes the cross-card ring
// and auto-escalates; "bust-out" trips the amount-vs-median critical signal; "clear" is a
// benign grocery run.
const PRESETS: Record<string, Record<string, unknown>> = {
  ring: {
    card_id: "card_999", amount: 350, merchant: "QuickPay Online",
    category: "online_retail", channel: "online", merchant_country: "CA",
    cardholder_country: "CA", timestamp: "2026-05-17T14:30:00",
  },
  bustout: {
    card_id: "card_001", amount: 1850, merchant: "BestBuy.ca",
    category: "electronics", channel: "online", merchant_country: "CA",
    cardholder_country: "CA",
  },
  clear: {
    card_id: "card_001", amount: 12.5, merchant: "Tim Hortons",
    category: "restaurant", channel: "in_person", merchant_country: "CA",
    cardholder_country: "CA",
  },
};

export function IngestForm({ onIngested, showToast }: IngestFormProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({
    card_id: "card_999", amount: "350", merchant: "QuickPay Online",
    category: "online_retail", channel: "online", merchant_country: "CA",
    timestamp: "2026-05-17T14:30:00",
  });
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: string, v: string) => setForm((p) => ({ ...p, [k]: v }));

  const applyPreset = (name: string) => {
    const p = PRESETS[name];
    setForm(Object.fromEntries(Object.entries(p).map(([k, v]) => [k, String(v)])));
  };

  const submit = async () => {
    setBusy(true);
    try {
      const body: Record<string, unknown> = { ...form, amount: parseFloat(form.amount) };
      const res = await createTransaction(body);
      setResult(res);
      const verb = res.decision.action.replace(/_/g, " ");
      showToast(
        `Ingested ${res.record.transaction_id} → ${verb}` +
          (res.notification ? " · analyst notified" : "")
      );
      onIngested();
    } catch (e) {
      showToast(`Ingest failed: ${e}`);
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button className="ingest-toggle" onClick={() => setOpen(true)}>
        ＋ Simulate incoming transaction
      </button>
    );
  }

  return (
    <div className="ingest-form">
      <div className="ingest-header">
        <span>Simulate incoming transaction</span>
        <button className="ingest-close" onClick={() => setOpen(false)}>✕</button>
      </div>

      <div className="ingest-presets">
        <button onClick={() => applyPreset("ring")}>Ring burst</button>
        <button onClick={() => applyPreset("bustout")}>Bust-out</button>
        <button onClick={() => applyPreset("clear")}>Clear</button>
      </div>

      <div className="ingest-grid">
        <label><span>Card</span><input value={form.card_id} onChange={(e) => set("card_id", e.target.value)} /></label>
        <label><span>Amount</span><input value={form.amount} onChange={(e) => set("amount", e.target.value)} /></label>
        <label className="ingest-wide"><span>Merchant</span><input value={form.merchant} onChange={(e) => set("merchant", e.target.value)} /></label>
        <label><span>Category</span><input value={form.category} onChange={(e) => set("category", e.target.value)} /></label>
        <label>
          <span>Channel</span>
          <select value={form.channel} onChange={(e) => set("channel", e.target.value)}>
            <option value="online">online</option>
            <option value="in_person">in_person</option>
            <option value="atm">atm</option>
          </select>
        </label>
        <label><span>Merchant country</span><input value={form.merchant_country} onChange={(e) => set("merchant_country", e.target.value)} /></label>
        <label className="ingest-wide"><span>Timestamp (optional)</span><input value={form.timestamp} onChange={(e) => set("timestamp", e.target.value)} /></label>
      </div>

      <button className="ingest-submit" onClick={submit} disabled={busy}>
        {busy ? "Scoring…" : "Add transaction"}
      </button>

      {result && (
        <div className={`ingest-result routing-${result.decision.action}`}>
          <div className="ingest-result-action">
            {result.record.transaction_id} → <strong>{result.decision.action.replace(/_/g, " ")}</strong>
            {result.notification ? " · analyst notified ✉️" : ""}
          </div>
          <div className="ingest-result-score">
            score {result.record.fraud_score.toFixed(2)} · {result.decision.reason}
          </div>
          <ul className="ingest-trail">
            {result.decision.trail.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
