# JSON_CONTRACT — the schema both sides build against

> **Agreed in H0–H2. Frozen.** This is the single most important coordination artifact: it lets the
> detector and the UI build in parallel against stub data and integrate without surprises. Changes
> require a quick sync with both owners.

---

## Scored record (the core object)

Returned by `GET /transactions` (as an array) and `GET /transaction/{id}` (single).

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
  "review_status": "pending"     // "pending" | "approved" | "dismissed" | "escalated"
}
```

**Field rules**
- `reasons` is always present and non-empty for any row where `label == "fraud"`.
- `fraud_score` is fixed at scoring time; `label` and `review_status` are mutable.
- `reasons[].weight` sums (before normalization) to the raw score; the UI may show the ranked text
  only and ignore weights.

---

## `GET /transactions` — query params

| Param | Type | Meaning |
|---|---|---|
| `card_id` | string | filter to one card |
| `merchant` | string | substring match |
| `category` | string | exact |
| `reason` | string | filter to rows where a given signal fired |
| `min_score` / `max_score` | float | score range |
| `date_from` / `date_to` | ISO date | timestamp range |
| `status` | string | review_status filter |
| `sort` | string | default `score_desc` |

Response: `{ "count": 71, "results": [ <scored record>, ... ] }`

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
`edge.type` ∈ `"co_burst" | "shared_ip" | "shared_device"`.

## `POST /threshold`

```jsonc
// request
{ "fp_cost": 1, "fn_cost": 5 }   // ratio shifts the cutoff
// response
{ "threshold": 0.42, "old_flag_count": 71, "new_flag_count": 58 }
```

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
appended).

---

## Stub data

Until the real engine lands, the UI builds against `web/src/stub/transactions.stub.json` — a handful
of records in exactly this shape, including one of each pattern (a QuickPay row, a micro-burst row, a
bust-out row, an account-takeover row) and a couple of clears. Keep the stub in sync with this file.
