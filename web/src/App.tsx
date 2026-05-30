import { useState, useCallback } from "react";
import { ReviewQueue } from "./ReviewQueue";
import { RingGraph } from "./RingGraph";
import { Filters } from "./Filters";
import { IngestForm } from "./IngestForm";
import { TransactionFilters } from "./api";

export function App() {
  const [filters, setFilters] = useState<TransactionFilters>({});
  const [toast, setToast] = useState<{message: string, action?: () => void, id: number} | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const showToast = useCallback((message: string, action?: () => void) => {
    const id = Date.now();
    setToast({ message, action, id });
    setTimeout(() => {
      setToast((current) => current?.id === id ? null : current);
    }, 5000);
  }, []);

  const triggerRefresh = useCallback(() => {
    setRefreshTrigger(prev => prev + 1);
  }, []);

  return (
    <div className="app-container">
      <section className="left-panel">
        <div className="glass-panel">
          <Filters filters={filters} setFilters={setFilters} onThresholdChange={triggerRefresh} />
          <IngestForm onIngested={triggerRefresh} showToast={showToast} />
        </div>
        <div className="glass-panel queue-container">
          <ReviewQueue 
            filters={filters} 
            showToast={showToast} 
            refreshTrigger={refreshTrigger}
            onUpdate={triggerRefresh}
          />
        </div>
      </section>
      <aside className="right-panel">
        <div className="glass-panel graph-container">
          <RingGraph 
            onNodeClick={(id, type) => {
              if (type === 'merchant') setFilters({ merchant: id });
              else setFilters({ card_id: id });
            }} 
          />
        </div>
      </aside>
      
      {toast && (
        <div className="toast-container">
          <div className="toast">
            <span>{toast.message}</span>
            {toast.action && (
              <button className="toast-undo-btn" onClick={() => { toast.action!(); setToast(null); }}>
                Undo (U)
              </button>
            )}
          </div>
        </div>
      )}
      
      <div className="keyboard-legend">
        <span><kbd>A</kbd> Approve</span>
        <span><kbd>D</kbd> Dismiss</span>
        <span><kbd>E</kbd> Escalate</span>
        <span><kbd>J</kbd><kbd>K</kbd> Navigate</span>
        <span><kbd>U</kbd> Undo</span>
        <span><kbd>/</kbd> Search</span>
      </div>
    </div>
  );
}
