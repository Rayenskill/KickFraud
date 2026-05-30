import { useEffect, useState, useCallback, useRef } from "react";
import { fetchTransactions, review, postUndo, TransactionFilters } from "./api";
import type { ScoredRecord } from "./types";

interface ReviewQueueProps {
  filters: TransactionFilters;
  showToast: (msg: string, action?: () => void) => void;
  refreshTrigger: number;
  onUpdate: () => void;
}

export function ReviewQueue({ filters, showToast, refreshTrigger, onUpdate }: ReviewQueueProps) {
  const [records, setRecords] = useState<ScoredRecord[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Ref for keyboard handlers to access current state without stale closures
  const stateRef = useRef({ records, currentIndex });
  
  useEffect(() => {
    stateRef.current = { records, currentIndex };
  }, [records, currentIndex]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchTransactions(filters);
      setRecords(data);
      setCurrentIndex(0);
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

  const handleDecision = async (decision: "approve" | "dismiss" | "escalate") => {
    const { records, currentIndex } = stateRef.current;
    if (currentIndex >= records.length) return;
    
    const record = records[currentIndex];
    
    try {
      const res = await review(record.transaction_id, decision, "human_reviewer");
      
      const undoAction = async () => {
        try {
          await postUndo();
          showToast(`Undone decision on ${record.transaction_id}`);
          onUpdate(); // Trigger refresh to get restored data and correct counts
        } catch (e) {
          console.error("Undo failed", e);
        }
      };
      
      let msg = `${decision.charAt(0).toUpperCase() + decision.slice(1)} ${record.transaction_id}`;
      if (res.suppressed && res.suppressed.length > 0) {
        msg += ` (suppressed ${res.suppressed.length} similar)`;
      }
      
      showToast(msg, undoAction);
      
      // Auto-advance
      if (currentIndex < records.length - 1) {
        setCurrentIndex(prev => prev + 1);
      }
      
      // Update the record locally
      const updatedRecords = [...records];
      updatedRecords[currentIndex] = { ...record, review_status: decision + "ed" as any };
      setRecords(updatedRecords);
      
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
      // Don't trigger if user is typing in an input (like the search bar)
      if (document.activeElement?.tagName === "INPUT") return;
      
      const key = e.key.toLowerCase();
      
      if (key === "a") handleDecision("approve");
      else if (key === "d") handleDecision("dismiss");
      else if (key === "e") handleDecision("escalate");
      else if (key === "u") handleUndo();
      else if (key === "arrowup" || key === "k") {
        setCurrentIndex(prev => Math.max(0, prev - 1));
      } else if (key === "arrowdown" || key === "j") {
        setCurrentIndex(prev => Math.min(stateRef.current.records.length - 1, prev + 1));
      }
    };
    
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  if (loading) return <div style={{padding: 16}}>Loading queue...</div>;
  if (error) return <div style={{padding: 16, color: 'var(--danger)'}}>API Error: {error}</div>;
  if (records.length === 0) return <div style={{padding: 16}}>No transactions found for these filters.</div>;

  const currentRecord = records[currentIndex];
  const isReviewed = currentRecord.review_status !== "pending";

  return (
    <>
      <div className="queue-header">
        <h2 style={{fontSize: '1.1rem'}}>Review Queue</h2>
        <span style={{color: 'var(--text-muted)', fontSize: '0.9rem'}}>
          {currentIndex + 1} / {records.length}
        </span>
      </div>
      
      <div className="queue-list">
        <div className={`flag-card ${isReviewed ? 'reviewed' : 'active'}`} style={{opacity: isReviewed ? 0.6 : 1}}>
          <div className="flag-header">
            <div>
              <div className="flag-amount">${currentRecord.amount.toFixed(2)}</div>
              <div className="flag-merchant">{currentRecord.merchant} • {currentRecord.card_id}</div>
              <div style={{fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4}}>
                {new Date(currentRecord.timestamp).toLocaleString()} • {currentRecord.channel} • {currentRecord.merchant_country}
              </div>
            </div>
            <div className={`flag-score ${currentRecord.label === 'clear' ? 'clear' : ''}`}>
              Score: {currentRecord.fraud_score.toFixed(2)}
            </div>
          </div>
          
          {currentRecord.card_median > 0 && (
            <div style={{
              margin: '12px 0', 
              padding: '12px', 
              background: 'rgba(255,255,255,0.02)', 
              borderRadius: '6px',
              borderLeft: `3px solid ${currentRecord.amount > currentRecord.card_median * 10 ? 'var(--danger)' : 'var(--accent-blue)'}`
            }}>
              <strong style={{color: 'white'}}>Amount Context: </strong>
              <span>
                ${currentRecord.amount.toFixed(2)} is {(currentRecord.amount / currentRecord.card_median).toFixed(1)}× this card's median of ${currentRecord.card_median.toFixed(2)}
              </span>
            </div>
          )}
          
          <div className="flag-reasons">
            <strong style={{color: 'white', marginBottom: 4, display: 'block', fontSize: '0.9rem'}}>Flag Reasons:</strong>
            {currentRecord.reasons.length > 0 ? (
              currentRecord.reasons.map((r, i) => (
                <div key={i} className="reason-badge">
                  {r.text} <span style={{opacity: 0.7}}>({r.weight.toFixed(2)})</span>
                </div>
              ))
            ) : (
              <span style={{color: 'var(--text-muted)', fontSize: '0.9rem'}}>No specific fraud signals fired.</span>
            )}
          </div>
          
          {isReviewed && (
            <div style={{marginTop: 16, textAlign: 'right', color: 'var(--warning)', fontWeight: 600}}>
              Status: {currentRecord.review_status.toUpperCase()}
            </div>
          )}
        </div>
        
        {/* Peek at the next few records */}
        {records.slice(currentIndex + 1, currentIndex + 4).map((r, i) => (
          <div 
            key={r.transaction_id} 
            className="flag-card"
            onClick={() => setCurrentIndex(currentIndex + 1 + i)}
            style={{opacity: 0.5, cursor: 'pointer', display: 'flex', justifyContent: 'space-between'}}
          >
            <div>
              <span style={{fontWeight: 600, color: 'white'}}>${r.amount.toFixed(2)}</span> at {r.merchant}
            </div>
            <div className={`flag-score ${r.label === 'clear' ? 'clear' : ''}`}>
              {r.fraud_score.toFixed(2)}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
