# JSON_CONTRACT — the schema both sides build against

> **Agreed in H0–H2. v1 frozen; v2 additive.** This is the single most important coordination
> artifact: it lets the detector and the UI build in parallel against stub data and integrate without
> surprises. v1 is frozen — v2 only adds **new optional fields** and new endpoints, never breaks an
> existing one. Changes require a quick sync with both owners. Mirrored in
> [contract/scored_record.schema.json](../contract/scored_record.schema.json), `detector/schema.py`,
> and `web/src/types.ts`. See [API.md](API.md) for the endpoint surface.

---

## Scored record (the core object)

Returned by `GET /transactions` (as an array) and `GET /transaction/{id}` (single). Fields below the
blank line are **v2 additive optional** — present on ingested/AI-touched rows, absent otherwise.

```jsonc
{
  "transaction_id": "tx_001003",
  "card_id": "card_009",
  "timestamp": "2026-05-17T14:11:07Z",
  "amount": 835.40,
  "merchant": "QuickPay Online",
  "merchant_country": "CA",
  "category": "online_retail",
  "channel": "online",          // "online" | "in_person"
  "device_id": "dev_6b84a60e",  // nullable
  "ip_address": "172.58.128.27",// nullable

  "fraud_score": 0.88,           // float, sum of fired signal weights (normalized 0..1)
  "label": "fraud",              // "fraud" | "clear", derived from current threshold
  "reasons": [                   // ranked, highest contribution first
    {
      "signal": "merchant_burst_cross_card",
      "weight": 0.46,
      "text": "'QuickPay Online' hit by 7 cards >$200 in 72 min"
    },
    {
      "signal": "amount_vs_card_median",
      "weight": 0.42,
      "text": "$835 is 46× this card's median"
    }
  ],

  "card_median": 18.06,          // context for the UI's "amount vs median" widget
  "review_status": "pending",    // "pending" | "approved" | "dismissed" | "escalated"

  // ---- v2 additive (optional) ----
  "cardholder_country": "US",    // string; home country of the card
  "ai_summary": "Cross-card burst on a single merchant; escalate. — recommend escalate",
                                 // string | null; lazy Gemini narrative, cached + persisted
  "decision": {                  // RoutingDecision; present on ingested rows
    "action": "escalate",
    "notify": true,
    "trail": ["critical signal merchant_burst_cross_card fired"],
    "used_ai": false,
    "reason": "critical signal fired"
  },
  "notified": true               // boolean; an analyst alert was queued for this row
}
```

**Field rules**
- `reasons` is always present and non-empty for any row where `label == "fraud"`.
- `fraud_score` is fixed at scoring time; `label` and `review_status` are mutable.
- `reasons[].weight` sums (before normalization) to the raw score; the UI may show the ranked text
  only and ignore weights.
- `cardholder_country` — string; populated on ingest and in `/export`. Optional on v1 rows.
- `ai_summary` — `string | null`; the lazy Gemini reviewer narrative (1–2 sentences + recommended
  action). `null` until generated; absent when Gemini is disabled. Cached per `transaction_id` and
  persisted.
- `decision` — a `RoutingDecision` (below). Attached to ingested transactions; absent on plain v1
  rows.
- `notified` — boolean; `true` when an analyst alert was queued (mirrors `decision.notify`).

---

## `RoutingDecision` (v2)

The decision-tree result attached to ingested transactions. Pure — produced by
`detector/decision_tree.py` (`route()`), no web/db/network.

```jsonc
{
  "action": "escalate",   // "auto_clear" | "queue" | "escalate"
  "notify": true,         // True is the trigger for the analyst alert
  "trail": ["score 0.88 >= escalate_at 0.80"],  // ordered branch trace
  "used_ai": false,       // True only when Gemini was consulted as tie-breaker
  "reason": "score >= escalate_at"
}
```

**Branch order** (first match wins): (1) a critical signal fired → `escalate` + notify;
(2) `score >= 0.80` → `escalate` + notify; (3) `score < 0.42` → `auto_clear`; (4) borderline
`[0.42, 0.80)` → AI verdict `"high"` → `escalate` + notify, else `queue` (default to human review).
Critical signals: `merchant_burst_cross_card`, `amount_vs_card_median`.

---

## `Notification` (v2)

Emitted when the decision tree escalates a new transaction. **LOG/QUEUE ONLY** — the default
`"log"` transport records the doc (`sent: false`) and **never sends**; SMTP/email is a pluggable seam
left for later. See [API.md](API.md).

```jsonc
{
  "notification_id": "ntf_3c1f0a2b",
  "transaction_id": "tx_live_9f2a1c",
  "to": "fraud-analyst@example.com",
  "subject": "[FraudHunter] escalate — tx_live_9f2a1c (score 0.88)",
  "body": "Cross-card burst on QuickPay Online; escalate for review.",
  "action": "escalate",   // "auto_clear" | "queue" | "escalate"
  "score": 0.88,
  "transport": "log",     // default "log" — never sends
  "created_at": "2026-05-30T18:04:22Z",
  "sent": false           // always false under the "log" transport
}
```

---

## `GET /transactions` — query params

Served from the in-memory cache (loaded from Mongo at startup) for speed — no per-keystroke Atlas
round-trip.

| Param | Type | Meaning |
|---|---|---|
| `card_id` | string | filter to one card |
| `merchant` | string | substring match |
| `category` | string | exact |
| `reason` | string | filter to rows where a given signal fired |
| `channel` | string | `online` \| `in_person` |
| `min_score` / `max_score` | float | score range |
| `min_amount` / `max_amount` | float | amount range |
| `date_from` / `date_to` | ISO date | timestamp range |
| `status` | string | `review_status` filter |
| `action` | string | routing action filter — `auto_clear` \| `queue` \| `escalate` |
| `sort` | string | one of `score_desc`, `score_asc`, `amount_desc`, `amount_asc`, `date_desc`, `date_asc` (default `score_desc`) |

Response: `{ "count": 71, "results": [ <scored record>, ... ] }`

---

## `GET /transaction/{id}/summary` (v2)

Lazy Gemini narrative for one transaction — generated on demand, cached, and persisted to
`ai_summary`.

```jsonc
{
  "transaction_id": "tx_001003",
  "summary": "Cross-card burst on QuickPay Online suggests a coordinated ring; recommend escalate.",
  "enabled": true   // false when Gemini is not configured (summary is null)
}
```

---

## `POST /transactions` (v2)

Live ingestion. Required body fields: `card_id`, `amount`, `merchant`, `category`, `channel`,
`merchant_country`. `transaction_id` (`tx_live_<hex>`) and an ISO `timestamp` are auto-assigned if
absent. The row is scored against all rows (including itself), routed through the decision tree, and
an analyst alert is queued when the route notifies.

```jsonc
// request
{
  "card_id": "card_009",
  "amount": 835.40,
  "merchant": "QuickPay Online",
  "category": "online_retail",
  "channel": "online",
  "merchant_country": "CA"
}

// response
{
  "record": { /* full scored record, incl. v2 decision + notified */ },
  "decision": {
    "action": "escalate",
    "notify": true,
    "trail": ["critical signal merchant_burst_cross_card fired"],
    "used_ai": false,
    "reason": "critical signal fired"
  },
  "notification": { /* Notification doc, or null if not notified */ }
}
```

---

## `GET /notifications` (v2)

Newest-first list of queued analyst alerts (mirrors the Mongo `notifications` collection).

```jsonc
{ "count": 3, "results": [ <Notification>, ... ] }
```

---

## `POST /review/{id}`

```jsonc
// request
{ "decision": "dismiss", "reviewer": "alice" }   // "approve" | "dismiss" | "escalate"

// response
{
  "transaction_id": "tx_001003",
  "review_status": "dismissed",
  "suppressed": ["tx_000993", "tx_000994"],  // similar flags suppressed by the feedback loop
  "new_flag_count": 68,
  "audit_id": "aud_0042"
}
```

## `POST /undo`

Pops the last decision off the stack.
```jsonc
// response
{ "undone": "tx_001003", "restored_status": "pending", "new_flag_count": 71 }
```

## `GET /graph`

```jsonc
{
  "nodes": [
    { "id": "card_009", "type": "card", "flag_count": 1 },
    { "id": "QuickPay Online", "type": "merchant", "suspicious": true }
  ],
  "edges": [
    { "source": "card_009", "target": "QuickPay Online", "type": "co_burst", "weight": 7 },
    { "source": "card_015", "target": "card_047", "type": "shared_ip", "ip": "99.225.114.61" }
  ]
}
```
`edge.type` ∈ `"co_burst" | "shared_ip" | "shared_device" | "transaction"`. `"transaction"` (v2) is
the faint card→merchant backbone edge `build_graph` already emits.

## `POST /threshold`

```jsonc
// request
{ "fp_cost": 1, "fn_cost": 5 }   // ratio shifts the cutoff
// response
{ "threshold": 0.42, "old_flag_count": 71, "new_flag_count": 58 }
```

The threshold relabel is **cache-only** — it never re-scores and is not persisted.

## `GET /audit`

```jsonc
{
  "entries": [
    {
      "audit_id": "aud_0042",
      "transaction_id": "tx_001003",
      "reviewer": "alice",
      "decision": "dismiss",
      "reason_at_decision": "gift_card never seen on this card",
      "timestamp": "2026-05-30T18:04:22Z"
    }
  ]
}
```

## `GET /export`

Streams `transactions_flagged.csv` (all 1,000 rows, `is_fraud` / `fraud_score` / `fraud_reasons`
appended; v2 also populates `cardholder_country`).

---

## Stub data

Until the real engine lands, the UI builds against `web/src/stub/transactions.stub.json` — a handful
of records in exactly this shape, including one of each pattern (a QuickPay row, a micro-burst row, a
bust-out row, an account-takeover row) and a couple of clears. Keep the stub in sync with this file.
