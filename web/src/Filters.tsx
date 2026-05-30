// Search / filter / cost slider.
// TODO (H10-H14): wire query+label+min_score to fetchTransactions; cost slider -> POST /threshold.
export function Filters() {
  return (
    <div>
      <input placeholder="search merchant / card…" disabled />
      <label> cost ratio <input type="range" min={1} max={20} disabled /></label>
    </div>
  );
}
