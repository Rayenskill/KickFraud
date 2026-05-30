import { useEffect, useState, useRef } from "react";
import { TransactionFilters, postThreshold } from "./api";

interface FiltersProps {
  filters: TransactionFilters;
  setFilters: (
    f: TransactionFilters | ((prev: TransactionFilters) => TransactionFilters)
  ) => void;
  onThresholdChange: () => void;
}

export function Filters({
  filters,
  setFilters,
  onThresholdChange,
}: FiltersProps) {
  const [sensitivity, setSensitivity] = useState(50); // 0=lenient, 100=aggressive
  const [flagCount, setFlagCount] = useState<number | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.key === "/" &&
        document.activeElement !== searchRef.current
      ) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleSliderChange = async (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const val = parseInt(e.target.value);
    setSensitivity(val);

    // Map 0..100 sensitivity to fn_cost 1..20
    const fn_cost = Math.max(1, Math.round((val / 100) * 20));
    try {
      const res = await postThreshold(1, fn_cost);
      setFlagCount(res.new_flag_count);
      onThresholdChange();
    } catch (err) {
      console.error("Failed to update threshold", err);
    }
  };

  const sensitivityLabel =
    sensitivity < 30
      ? "Lenient"
      : sensitivity < 70
        ? "Balanced"
        : "Aggressive";

  return (
    <div className="filters-container">
      <input
        ref={searchRef}
        type="text"
        placeholder="Search merchant or card... (press /)"
        value={filters.merchant || filters.card_id || ""}
        onChange={(e) => {
          const val = e.target.value;
          if (val.startsWith("card_")) {
            setFilters((prev) => ({
              ...prev,
              card_id: val,
              merchant: undefined,
            }));
          } else {
            setFilters((prev) => ({
              ...prev,
              merchant: val,
              card_id: undefined,
            }));
          }
        }}
      />

      <div className="sensitivity-group">
        <div className="sensitivity-header">
          <span className="sensitivity-label">Fraud Sensitivity</span>
          <span className={`sensitivity-value sensitivity-${sensitivityLabel.toLowerCase()}`}>
            {sensitivityLabel}
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={100}
          value={sensitivity}
          onChange={handleSliderChange}
          className="sensitivity-slider"
        />
        <div className="sensitivity-hints">
          <span>Fewer flags</span>
          <span>More flags</span>
        </div>
        {flagCount !== null && (
          <div className="sensitivity-count">
            {flagCount} transactions flagged
          </div>
        )}
      </div>

      {(filters.merchant || filters.card_id) && (
        <button className="clear-btn" onClick={() => setFilters({})}>
          Clear Filters
        </button>
      )}
    </div>
  );
}
