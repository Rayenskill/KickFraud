import { useEffect, useState, useRef } from "react";
import { TransactionFilters, postThreshold } from "./api";

interface FiltersProps {
  filters: TransactionFilters;
  setFilters: (
    f: TransactionFilters | ((prev: TransactionFilters) => TransactionFilters)
  ) => void;
  onThresholdChange: () => void;
}

// Kept in sync with the dataset (challenge_brief) + detector/signals.py.
const CATEGORIES = [
  "grocery", "gas", "restaurant", "online_retail", "electronics", "travel",
  "subscription", "entertainment", "utilities", "atm", "gift_card",
];
const SIGNALS = [
  "merchant_burst_cross_card", "amount_vs_card_median", "velocity_burst",
  "atypical_category_for_card", "atypical_country_for_card", "high_risk_merchant",
  "shared_ip_across_cards", "shared_device_across_cards", "new_device_or_ip_for_card",
];
const SORTS: { value: string; label: string }[] = [
  { value: "score_desc", label: "Score ↓" },
  { value: "score_asc", label: "Score ↑" },
  { value: "amount_desc", label: "Amount ↓" },
  { value: "amount_asc", label: "Amount ↑" },
  { value: "date_desc", label: "Newest" },
  { value: "date_asc", label: "Oldest" },
];

export function Filters({ filters, setFilters, onThresholdChange }: FiltersProps) {
  const [sensitivity, setSensitivity] = useState(50); // 0=lenient, 100=aggressive
  const [flagCount, setFlagCount] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
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
    const val = parseInt(e.target.value);
    setSensitivity(val);
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
    sensitivity < 30 ? "Lenient" : sensitivity < 70 ? "Balanced" : "Aggressive";

  // Set a filter field; empty string / NaN clears it (becomes undefined).
  const set = (key: keyof TransactionFilters, value: string) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === "" ? undefined : value,
    }));
  };
  const setNum = (key: keyof TransactionFilters, value: string) => {
    const n = parseFloat(value);
    setFilters((prev) => ({
      ...prev,
      [key]: value === "" || Number.isNaN(n) ? undefined : n,
    }));
  };

  const activeCount = [
    filters.category, filters.channel, filters.status, filters.reason,
    filters.min_score, filters.max_score, filters.min_amount, filters.max_amount,
    filters.date_from, filters.date_to, filters.action,
  ].filter((v) => v !== undefined && v !== "").length;

  const hasAnyFilter = activeCount > 0 || filters.merchant || filters.card_id;

  return (
    <div className="filters-container">
      <div className="filters-row">
        <input
          ref={searchRef}
          type="text"
          className="filter-search"
          placeholder="Search merchant or card... (press /)"
          value={filters.merchant || filters.card_id || ""}
          onChange={(e) => {
            const val = e.target.value;
            if (val.startsWith("card_")) {
              setFilters((prev) => ({ ...prev, card_id: val, merchant: undefined }));
            } else {
              setFilters((prev) => ({ ...prev, merchant: val, card_id: undefined }));
            }
          }}
        />
        <select
          className="filter-select"
          value={filters.sort || "score_desc"}
          onChange={(e) => set("sort", e.target.value)}
          title="Sort by"
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
        <button
          className={`toggle-btn ${showAdvanced ? "active" : ""}`}
          onClick={() => setShowAdvanced((s) => !s)}
        >
          Filters{activeCount > 0 ? ` (${activeCount})` : ""}
        </button>
      </div>

      {showAdvanced && (
        <div className="filters-grid">
          <label>
            <span>Category</span>
            <select value={filters.category || ""} onChange={(e) => set("category", e.target.value)}>
              <option value="">Any</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label>
            <span>Channel</span>
            <select value={filters.channel || ""} onChange={(e) => set("channel", e.target.value)}>
              <option value="">Any</option>
              <option value="online">online</option>
              <option value="in_person">in_person</option>
              <option value="atm">atm</option>
            </select>
          </label>
          <label>
            <span>Status</span>
            <select value={filters.status || ""} onChange={(e) => set("status", e.target.value)}>
              <option value="">Any</option>
              <option value="pending">pending</option>
              <option value="approved">approved</option>
              <option value="dismissed">dismissed</option>
              <option value="escalated">escalated</option>
            </select>
          </label>
          <label className="filter-wide">
            <span>Signal fired</span>
            <select value={filters.reason || ""} onChange={(e) => set("reason", e.target.value)}>
              <option value="">Any</option>
              {SIGNALS.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Min score</span>
            <input type="number" step="0.05" min="0" max="1"
              value={filters.min_score ?? ""} onChange={(e) => setNum("min_score", e.target.value)} />
          </label>
          <label>
            <span>Max score</span>
            <input type="number" step="0.05" min="0" max="1"
              value={filters.max_score ?? ""} onChange={(e) => setNum("max_score", e.target.value)} />
          </label>
          <label>
            <span>Min amount</span>
            <input type="number" step="1" min="0"
              value={filters.min_amount ?? ""} onChange={(e) => setNum("min_amount", e.target.value)} />
          </label>
          <label>
            <span>Max amount</span>
            <input type="number" step="1" min="0"
              value={filters.max_amount ?? ""} onChange={(e) => setNum("max_amount", e.target.value)} />
          </label>
          <label>
            <span>From date</span>
            <input type="date" value={filters.date_from || ""} onChange={(e) => set("date_from", e.target.value)} />
          </label>
          <label>
            <span>To date</span>
            <input type="date" value={filters.date_to || ""} onChange={(e) => set("date_to", e.target.value)} />
          </label>
        </div>
      )}

      <div className="sensitivity-group">
        <div className="sensitivity-header">
          <span className="sensitivity-label">Fraud Sensitivity</span>
          <span className={`sensitivity-value sensitivity-${sensitivityLabel.toLowerCase()}`}>
            {sensitivityLabel}
          </span>
        </div>
        <input
          type="range" min={0} max={100} value={sensitivity}
          onChange={handleSliderChange} className="sensitivity-slider"
        />
        <div className="sensitivity-hints">
          <span>Fewer flags</span>
          <span>More flags</span>
        </div>
        {flagCount !== null && (
          <div className="sensitivity-count">{flagCount} transactions flagged</div>
        )}
      </div>

      {hasAnyFilter && (
        <button className="clear-btn" onClick={() => setFilters({})}>
          Clear Filters
        </button>
      )}
    </div>
  );
}
