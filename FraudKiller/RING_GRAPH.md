# RING_GRAPH — the signature creative feature

This is the demo centerpiece. It makes the **cross-card processor attack (P4)** — invisible in any
per-transaction view — obvious in a single glance, and directly showcases why cross-card aggregation
matters.

---

## What it is
A **force-directed graph** (react-force-graph / d3) rendered in `web/RingGraph.tsx`, fed by
`GET /graph`.

- **Nodes:** cards + suspicious merchants.
- **Edges (three types):**
  - **`co_burst`** — cards that hit the same merchant within the same short window. *This is the edge
    type that makes the graph meaningful.*
  - **`shared_ip`** — cards sharing an IP (the single such pair in the data).
  - **`shared_device`** — cards sharing a device (none — raw device reuse is ~0).

## The money shot
The **QuickPay Online** attack renders as **two hubs**, one per coordinated burst:

- **May 5 hub** — QuickPay center, **6 card nodes** radiating off it (cards 032, 037, 002, 038, 039,
  046), all charged >$200 within ~72 minutes (02:15–03:27).
- **May 17 hub** — QuickPay center, **7 card nodes** (cards 037, 009, 030, 036, 029, 040, 007), all
  >$200 within ~72 minutes (14:10–15:22).

card_037 appears in **both** hubs — a bridge node that's a nice "look, a repeat offender" beat. No
single one of these cards looks unusual alone; together each cluster is an unmistakable coordinated
attack. The graph turns a dozen scattered >$200 charges into two clean shapes.

> **Note:** an earlier draft described this as "16 cards on May 24." That was wrong — May 24 has a
> single $92.60 QuickPay charge. The real attack is the two May 5 / May 17 bursts above. The graph is
> built from the data, so it shows the truth regardless of the old prose.

## Why co_burst is non-optional
Raw device reuse across cards ≈ 0 and IP reuse is a single pair. If the graph only drew device/IP
edges it would be nearly empty and useless. The **co_burst edge** — derived from the per-(merchant,
sliding-window) distinct-card aggregate, gated to high-value (>$200) charges — is what gives the
graph its signal. It must ship; it is not a nice-to-have. (Recorded as a risk in `RISKS.md`.)

## Interaction
- **Click a node → filter the queue** to that node's transactions. Click QuickPay → the queue shows
  the coordinated >$200 flags from both bursts. Click a card → its flagged activity.
- Suspicious merchants are visually distinct (color/size) so the hubs stand out without hunting.
- A **mini snippet** of this graph, centered on the current flag's card/merchant, is embedded in the
  review queue (see `REVIEWER_UX.md`) so cross-card context is always one glance away.

## Data shape
See `JSON_CONTRACT.md` → `GET /graph`. Nodes carry `type` (`card` | `merchant`) and a `suspicious`
/`flag_count` hint for styling; edges carry `type` and a `weight` (e.g. co_burst weight = number of
cards in the burst, 6 and 7 here).

## Demo beat
In the 7-minute run, the graph is beat #3: load queue → explain a reason → **open graph, the two
QuickPay rings appear (and card_037 bridging both)** → dismiss-and-watch-it-learn → cost slider. It's
the visual that lands the "we detect coordinated fraud you can't see per-transaction" claim. See
`DEMO_SCRIPT.md`.
