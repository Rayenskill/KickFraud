import { useState, useCallback, useEffect, useRef } from "react";
import { ReviewQueue } from "./ReviewQueue";
import { RingGraph } from "./RingGraph";
import { Filters } from "./Filters";
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

  const [leftWidth, setLeftWidth] = useState(380);
  const [isDragging, setIsDragging] = useState(false);
  const leftPanelRef = useRef<HTMLElement>(null);

  const startDragging = useCallback(() => {
    setIsDragging(true);
  }, []);

  const onDrag = useCallback((e: MouseEvent) => {
    if (!isDragging || !leftPanelRef.current) return;
    const newWidth = Math.max(300, Math.min(e.clientX, 800));
    leftPanelRef.current.style.width = `${newWidth}px`;
    leftPanelRef.current.style.flex = `0 0 ${newWidth}px`;
  }, [isDragging]);

  const stopDragging = useCallback(() => {
    setIsDragging(false);
    if (leftPanelRef.current) {
      const currentWidth = parseInt(leftPanelRef.current.style.width);
      if (!isNaN(currentWidth)) {
        setLeftWidth(currentWidth);
      }
    }
  }, []);



  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', onDrag);
      window.addEventListener('mouseup', stopDragging);
    } else {
      window.removeEventListener('mousemove', onDrag);
      window.removeEventListener('mouseup', stopDragging);
    }
    return () => {
      window.removeEventListener('mousemove', onDrag);
      window.removeEventListener('mouseup', stopDragging);
    };
  }, [isDragging, onDrag, stopDragging]);

  return (
    <div className="app-container" style={{ userSelect: isDragging ? 'none' : 'auto' }}>
      <section ref={leftPanelRef} className="left-panel" style={{ width: leftWidth, flex: `0 0 ${leftWidth}px` }}>
        <div className="glass-panel">
          <Filters filters={filters} setFilters={setFilters} onThresholdChange={triggerRefresh} />
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
      
      <div 
        className={`resizer ${isDragging ? 'dragging' : ''}`} 
        onMouseDown={startDragging}
        title="Drag to resize"
      />

      <aside className="right-panel">
        <div className="glass-panel graph-container">
          <RingGraph 
            refreshTrigger={refreshTrigger}
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
