import { useEffect, useState, useRef } from "react";
import { TransactionFilters, postThreshold } from "./api";

interface FiltersProps {
  filters: TransactionFilters;
  setFilters: (f: TransactionFilters | ((prev: TransactionFilters) => TransactionFilters)) => void;
  onThresholdChange: () => void;
}

export function Filters({ filters, setFilters, onThresholdChange }: FiltersProps) {
  const [costRatio, setCostRatio] = useState(5); // fn_cost / fp_cost, default 5
  const [flagCount, setFlagCount] = useState<number | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement !== searchRef.current) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleSliderChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const ratio = parseInt(e.target.value);
    setCostRatio(ratio);
    try {
      const res = await postThreshold(1, ratio);
      setFlagCount(res.new_flag_count);
      onThresholdChange();
    } catch (err) {
      console.error("Failed to update threshold", err);
    }
  };

  return (
    <div className="filters-container">
      <input 
        ref={searchRef}
        type="text" 
        placeholder="Search merchant or card (/ to focus)" 
        value={filters.merchant || filters.card_id || ""}
        onChange={(e) => {
          const val = e.target.value;
          // Simple heuristic: if it looks like a card id, search card, else merchant
          if (val.startsWith("card_")) {
            setFilters(prev => ({ ...prev, card_id: val, merchant: undefined }));
          } else {
            setFilters(prev => ({ ...prev, merchant: val, card_id: undefined }));
          }
        }}
      />
      <div className="cost-slider-group">
        <label>
          <span>FP / FN Cost Ratio</span>
          <span>1:{costRatio}</span>
        </label>
        <input 
          type="range" 
          min={1} 
          max={20} 
          value={costRatio} 
          onChange={handleSliderChange} 
        />
        {flagCount !== null && (
          <div style={{fontSize: '0.8rem', color: 'var(--accent-blue)', marginTop: 4}}>
            Flags: {flagCount}
          </div>
        )}
      </div>
      {(filters.merchant || filters.card_id) && (
        <button 
          onClick={() => setFilters({})}
          style={{
            background: 'transparent',
            border: '1px solid var(--border-color)',
            color: 'var(--text-main)',
            padding: '6px 12px',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '0.85rem'
          }}
        >
          Clear Filters
        </button>
      )}
    </div>
  );
}
