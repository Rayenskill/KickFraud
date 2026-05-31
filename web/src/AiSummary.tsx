import { useEffect, useState } from "react";
import { fetchSummary } from "./api";
import type { ScoredRecord } from "./types";

// Lazy Gemini risk summary for the currently-open flag. The endpoint caches server-side,
// so navigation is cheap after the first view. If Gemini is disabled (no API key), the
// panel hides itself once it learns `enabled === false`.
export function AiSummary({ record }: { record: ScoredRecord }) {
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState<string | null>(record.ai_summary ?? null);
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setText(record.ai_summary ?? null);
    fetchSummary(record.transaction_id)
      .then((res) => {
        if (cancelled) return;
        setText(res.summary);
        setEnabled(res.enabled);
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [record.transaction_id]);

  if (!loading && !enabled && !text) return null;

  const routing = record.decision;

  return (
    <div className="ai-summary">
      <div className="ai-summary-header">✨ AI summary</div>
      {loading ? (
        <div className="ai-summary-loading">Analyzing…</div>
      ) : text ? (
        <div className="ai-summary-text">{text}</div>
      ) : (
        <div className="ai-summary-loading">No AI summary available.</div>
      )}
      {routing && (
        <div className={`routing-chip routing-${routing.action}`}>
          decision tree: {routing.action.replace(/_/g, " ")}
          {routing.notify ? " · analyst notified" : ""}
        </div>
      )}
    </div>
  );
}
