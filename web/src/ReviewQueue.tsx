import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import {
  fetchTransactions,
  review,
  postUndo,
  TransactionFilters,
} from "./api";
import { AiSummary } from "./AiSummary";
import type { ScoredRecord } from "./types";

interface ReviewQueueProps {
  filters: TransactionFilters;
  showToast: (msg: string, action?: () => void) => void;
  refreshTrigger: number;
  onUpdate: () => void;
}

function riskLevel(score: number): { label: string; cls: string } {
  if (score >= 0.8) return { label: "Critical", cls: "risk-critical" };
  if (score >= 0.6) return { label: "High", cls: "risk-high" };
  if (score >= 0.42) return { label: "Medium", cls: "risk-medium" };
  return { label: "Low", cls: "risk-low" };
}

type ViewMode = "triage" | "table";
type SortMode = "score_desc" | "score_asc" | "amount_desc" | "date_desc";
type FilterRisk = "flagged" | "all" | "critical" | "high" | "medium" | "low";

export function ReviewQueue({
  filters,
  showToast,
  refreshTrigger,
  onUpdate,
}: ReviewQueueProps) {
  const [allRecords, setAllRecords] = useState<ScoredRecord[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedReasons, setExpandedReasons] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [sortMode, setSortMode] = useState<SortMode>("score_desc");
  const [filterRisk, setFilterRisk] = useState<FilterRisk>("flagged");

  const records = useMemo(() => {
    let filtered = allRecords;
    if (filterRisk !== "all") {
      filtered = filtered.filter(r => {
        if (filterRisk === "flagged") return r.label === "fraud";
        if (filterRisk === "critical") return r.fraud_score >= 0.8;
        if (filterRisk === "high") return r.fraud_score >= 0.6 && r.fraud_score < 0.8;
        if (filterRisk === "medium") return r.fraud_score >= 0.42 && r.fraud_score < 0.6;
        if (filterRisk === "low") return r.fraud_score < 0.42;
        return true;
      });
    }

    return [...filtered].sort((a, b) => {
      if (sortMode === "score_desc") return b.fraud_score - a.fraud_score;
      if (sortMode === "score_asc") return a.fraud_score - b.fraud_score;
      if (sortMode === "amount_desc") return b.amount - a.amount;
      if (sortMode === "date_desc") return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
      return 0;
    });
  }, [allRecords, sortMode, filterRisk]);

  const stateRef = useRef({ records, currentIndex });

  useEffect(() => {
    stateRef.current = { records, currentIndex };
  }, [records, currentIndex]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchTransactions(filters);
      setAllRecords(data);
      setCurrentIndex(0);
      setExpandedReasons(false);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [filters, refreshTrigger]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleDecision = async (
    decision: "approve" | "dismiss" | "escalate"
  ) => {
    const { records, currentIndex } = stateRef.current;
    if (currentIndex >= records.length) return;
    const record = records[currentIndex];
    try {
      const res = await review(
        record.transaction_id,
        decision,
        "human_reviewer"
      );
      const undoAction = async () => {
        try {
          await postUndo();
          showToast(`Undone decision on ${record.transaction_id}`);
          onUpdate();
        } catch (e) {
          console.error("Undo failed", e);
        }
      };
      let msg = `${decision.charAt(0).toUpperCase() + decision.slice(1)} ${record.transaction_id}`;
      if (res.suppressed && res.suppressed.length > 0) {
        msg += ` (suppressed ${res.suppressed.length} similar)`;
      }
      showToast(msg, undoAction);
      if (currentIndex < records.length - 1) {
        setCurrentIndex((prev) => prev + 1);
      }
      const updatedRecords = [...allRecords];
      const realIndex = allRecords.findIndex(r => r.transaction_id === record.transaction_id);
      if (realIndex >= 0) {
        updatedRecords[realIndex] = {
          ...record,
          review_status: (decision + "ed") as any,
        };
        setAllRecords(updatedRecords);
      }
      setExpandedReasons(false);
      onUpdate();
    } catch (e) {
      console.error("Review failed", e);
      showToast(`Error: ${e}`);
    }
  };

  const handleUndo = async () => {
    try {
      const res = await postUndo();
      if (res.undone) {
        showToast(`Undone decision on ${res.undone}`);
        onUpdate();
      }
    } catch (e) {
      console.error("Undo failed", e);
      showToast(`Undo Error: ${e}`);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (document.activeElement?.tagName === "INPUT") return;
      const key = e.key.toLowerCase();
      if (viewMode === "triage") {
        if (key === "a") handleDecision("approve");
        else if (key === "d") handleDecision("dismiss");
        else if (key === "e") handleDecision("escalate");
        else if (key === "u") handleUndo();
      }
      if (key === "arrowup" || key === "k") {
        setCurrentIndex((prev) => Math.max(0, prev - 1));
        setExpandedReasons(false);
      } else if (key === "arrowdown" || key === "j") {
        setCurrentIndex((prev) =>
          Math.min(stateRef.current.records.length - 1, prev + 1)
        );
        setExpandedReasons(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [viewMode]);

  if (loading)
    return (
      <div style={{ padding: 16, color: "var(--text-muted)" }}>
        Loading queue...
      </div>
    );
  if (error)
    return (
      <div style={{ padding: 16, color: "var(--danger)" }}>
        API Error: {error}
      </div>
    );
  if (records.length === 0)
    return (
      <div style={{ padding: 16, color: "var(--text-muted)" }}>
        No transactions match these filters.
      </div>
    );

  // Risk counts
  const riskCounts = {
    critical: allRecords.filter((r) => r.fraud_score >= 0.8).length,
    high: allRecords.filter((r) => r.fraud_score >= 0.6 && r.fraud_score < 0.8).length,
    medium: allRecords.filter((r) => r.fraud_score >= 0.42 && r.fraud_score < 0.6).length,
    low: allRecords.filter((r) => r.fraud_score < 0.42).length,
  };

  return (
    <>
      {/* Header */}
      <div className="queue-header">
        {/* Row 1: title + risk summary */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <h2 style={{ fontSize: "1.05rem", fontWeight: 700, color: "white" }}>
            Transactions
          </h2>
          <div className="risk-summary">
            {riskCounts.critical > 0 && (
              <span className="risk-dot risk-critical">{riskCounts.critical} critical</span>
            )}
            {riskCounts.high > 0 && (
              <span className="risk-dot risk-high">{riskCounts.high} high</span>
            )}
            {riskCounts.medium > 0 && (
              <span className="risk-dot risk-medium">{riskCounts.medium} med</span>
            )}
          </div>
        </div>

        {/* Row 2: controls toolbar */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          {/* Filter dropdown */}
          <select
            value={filterRisk}
            onChange={e => setFilterRisk(e.target.value as FilterRisk)}
            className="ctrl-select"
          >
            <option value="flagged">🚩 Flagged</option>
            <option value="all">All</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          {/* Sort dropdown */}
          <select
            value={sortMode}
            onChange={e => setSortMode(e.target.value as SortMode)}
            className="ctrl-select"
          >
            <option value="score_desc">↓ Score</option>
            <option value="score_asc">↑ Score</option>
            <option value="amount_desc">↓ Amount</option>
            <option value="date_desc">🕐 Recent</option>
          </select>

          {/* Spacer */}
          <div style={{ flex: 1 }} />

          {/* View toggle */}
          <div className="view-mode-toggle">
            <button
              className={viewMode === "table" ? "view-btn active" : "view-btn"}
              onClick={() => setViewMode("table")}
              title="Table view"
            >
              ≡ Table
            </button>
            <button
              className={viewMode === "triage" ? "view-btn active" : "view-btn"}
              onClick={() => setViewMode("triage")}
              title="Triage view"
            >
              ⚡ Triage
            </button>
          </div>
        </div>

        <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginTop: 4, display: "block" }}>
          Showing {records.length} of {allRecords.length}
        </span>
      </div>

      {/* ===== TABLE VIEW ===== */}
      {viewMode === "table" && (
        <div className="table-wrapper">
          <table className="txn-table">
            <thead>
              <tr>
                <th>Risk</th>
                <th>Score</th>
                <th>Amount</th>
                <th>Merchant</th>
                <th>Card</th>
                <th>Date</th>
                <th>Signals</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r, i) => {
                const rk = riskLevel(r.fraud_score);
                return (
                  <tr
                    key={r.transaction_id}
                    className={`txn-row ${i === currentIndex ? "selected" : ""} ${r.review_status !== "pending" ? "reviewed" : ""}`}
                    onClick={() => {
                      setCurrentIndex(i);
                      setViewMode("triage");
                    }}
                  >
                    <td>
                      <span className={`risk-pip ${rk.cls}`} />
                    </td>
                    <td className="col-score">{r.fraud_score.toFixed(2)}</td>
                    <td className="col-amount">${r.amount.toFixed(2)}</td>
                    <td className="col-merchant">{r.merchant}</td>
                    <td className="col-card">{r.card_id}</td>
                    <td className="col-date">
                      {new Date(r.timestamp).toLocaleDateString()}
                    </td>
                    <td className="col-signals">
                      {r.reasons.length > 0
                        ? r.reasons
                            .slice(0, 2)
                            .map((s) => s.signal.replace(/_/g, " "))
                            .join(", ")
                        : "-"}
                      {r.reasons.length > 2 && ` +${r.reasons.length - 2}`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ===== TRIAGE VIEW ===== */}
      {viewMode === "triage" && (
        <div className="queue-list">
          {(() => {
            const currentRecord = records[currentIndex];
            const isReviewed = currentRecord.review_status !== "pending";
            const risk = riskLevel(currentRecord.fraud_score);

            return (
              <>
                <div
                  className={`flag-card ${isReviewed ? "reviewed" : "active"}`}
                  style={{ opacity: isReviewed ? 0.5 : 1 }}
                >
                  <div className="flag-header">
                    <div style={{ flex: 1 }}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "baseline",
                          gap: 8,
                        }}
                      >
                        <span className="flag-amount">
                          ${currentRecord.amount.toFixed(2)}
                        </span>
                        <span className={`risk-badge ${risk.cls}`}>
                          {risk.label}
                        </span>
                      </div>
                      <div className="flag-merchant">
                        {currentRecord.merchant} &middot;{" "}
                        {currentRecord.card_id}
                      </div>
                      <div className="flag-meta">
                        {new Date(
                          currentRecord.timestamp
                        ).toLocaleDateString()}{" "}
                        &middot; {currentRecord.channel} &middot;{" "}
                        {currentRecord.merchant_country}
                      </div>
                    </div>
                    <div className="flag-score-num">
                      {currentRecord.fraud_score.toFixed(2)}
                    </div>
                  </div>

                  {currentRecord.card_median > 0 &&
                    currentRecord.amount > currentRecord.card_median * 2 && (
                      <div className="amount-context">
                        <span className="amount-context-icon">!</span>
                        {(
                          currentRecord.amount / currentRecord.card_median
                        ).toFixed(1)}
                        x card median ($
                        {currentRecord.card_median.toFixed(0)})
                      </div>
                    )}

                  {currentRecord.reasons.length > 0 && (
                    <div className="flag-reasons-compact">
                      {currentRecord.reasons
                        .slice(0, expandedReasons ? undefined : 3)
                        .map((r, i) => (
                          <span key={i} className="reason-tag">
                            {r.signal.replace(/_/g, " ")}
                          </span>
                        ))}
                      {currentRecord.reasons.length > 3 &&
                        !expandedReasons && (
                          <button
                            className="reason-expand-btn"
                            onClick={() => setExpandedReasons(true)}
                          >
                            +{currentRecord.reasons.length - 3} more
                          </button>
                        )}
                    </div>
                  )}

                  <AiSummary record={currentRecord} />

                  {isReviewed && (
                    <div className="reviewed-status">
                      {currentRecord.review_status.toUpperCase()}
                    </div>
                  )}
                </div>

                {/* Peek upcoming */}
                {records
                  .slice(currentIndex + 1, currentIndex + 5)
                  .map((r, i) => {
                    const rk = riskLevel(r.fraud_score);
                    return (
                      <div
                        key={r.transaction_id}
                        className="flag-card flag-card-peek"
                        onClick={() => {
                          setCurrentIndex(currentIndex + 1 + i);
                          setExpandedReasons(false);
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                          }}
                        >
                          <span className={`risk-pip ${rk.cls}`} />
                          <span className="peek-amount">
                            ${r.amount.toFixed(2)}
                          </span>
                          <span className="peek-merchant">{r.merchant}</span>
                        </div>
                        <span className="peek-score">
                          {r.fraud_score.toFixed(2)}
                        </span>
                      </div>
                    );
                  })}
              </>
            );
          })()}
        </div>
      )}
    </>
  );
}
