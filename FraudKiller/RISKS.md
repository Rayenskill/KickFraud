# RISKS & WATCH-OUTS

| Risk | Impact | Mitigation |
|---|---|---|
| **Over-flagging tanks precision** | Detection score craters; reviewer drowns in false positives | Geo-mismatch and foreign `merchant_country` are **traps**. Require *combined* deviations (category **and** country) and per-card baselines, never absolute thresholds. Two pytest trap cases guard this. |
| **UI/detector integration stall** | Two tracks block each other; integration eats the final hours | **Freeze the JSON contract at H0–H2** and build the UI against stub data matching it. Real engine drops in behind the same shape. |
| **Graph sparsity** | The signature feature renders nearly empty and underwhelms | Raw device/IP edges are near-zero (device reuse 0, IP reuse 1 pair). The **co_burst edge type is what makes the graph meaningful and must ship** — not optional. |
| **Demo time (7 min)** | Great tool, fumbled pitch, lost points | **Script and rehearse** the demo: queue → reason → ring graph reveals QuickPay → dismiss-and-watch-it-learn → cost slider. See `DEMO_SCRIPT.md`. |
| **Tuning overfits the known band** | F1 looks great on the private band, logic is actually brittle | Tune against the band but keep signals grounded in the *pattern* (velocity, baseline deviation), not the band itself. The transaction_id cue never becomes a signal. |
| **Scratch files leak into submission** | Looks sloppy; "engineering craft" is 20 pts | Delete `Downloads\_an*.txt` and `/tmp/*.py` during H18–24 cleanup; verify the repo tree before submitting. |
| **Scope creep into skipped items** | Time bleeds from the 80 pts that matter (detection + reviewer UX) | `IMPLEMENTATION_PLAN.md` lists explicit skips (ML, auth, DB, streaming, mobile, Docker). Hold the line. |
| **Threshold re-scoring confusion** | Slider feels slow or labels go inconsistent | Slider **never re-scores** — scores are fixed at startup; only the cutoff moves. Keep that invariant. |
