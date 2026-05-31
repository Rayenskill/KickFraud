# Notifications — analyst alerting

The "should we email the fraud team?" output of the v2 pipeline. When the decision tree escalates a
newly-ingested transaction, the system **records an analyst alert** — but, by design, does not send
one yet. Alerts are LOG/QUEUE ONLY: persisted to Mongo + an in-memory list + the audit log, with a
single pluggable seam (`_send()`) left for SMTP or an email API later. Lives in `api/notifications.py`
(network-bearing code stays in `api/`, never `detector/`).

## When it fires

Notifications are triggered on **ingestion only** (`POST /transactions`). After the decision tree
routes a new transaction, `api/main.py` checks `decision.notify`:

```python
if decision.notify:
    notification = notifications.notify_analyst(doc, decision)
    STATE.system_event(doc["transaction_id"], decision.action, decision.reason)
```

`notify == True` is the trigger. Per [DECISION_TREE.md](DECISION_TREE.md), `route()` sets it on every
**escalate** branch — a critical signal fired, `score >= 0.80`, or a borderline score the AI
tie-breaker classified `high`. `auto_clear` and `queue` never notify. So one ingest yields at most one
alert, and the `system_event` audit entry (a non-human, decision-tree action) is written alongside it.

| Decision action | `notify` | Alert recorded? |
| --- | --- | --- |
| `escalate` | `True`  | yes |
| `queue`    | `False` | no  |
| `auto_clear` | `False` | no |

## Notification shape

`notify_analyst(record, decision)` builds the contract-v2 `Notification` doc (see
[JSON_CONTRACT.md](JSON_CONTRACT.md)):

| Field | Type | Notes |
| --- | --- | --- |
| `notification_id` | string | `ntf_<hex>` |
| `transaction_id`  | string | the escalated txn |
| `to`        | string | `FRAUD_ANALYST_EMAIL` |
| `subject`   | string | `[Fraud Hunter] Escalation: <id> ($<amount>, score <s>)` |
| `body`      | string | card, merchant/category/country/channel, score, top signal, routing trail |
| `action`    | string | `decision.action` (`escalate`) |
| `score`     | number | `fraud_score` |
| `transport` | string | `NOTIFY_TRANSPORT` (`log`) |
| `created_at`| string | ISO-8601 UTC |
| `sent`      | boolean | `False` under the `log` transport |

## The "log" transport — record, don't send

The shipped transport is **`log`**. `notify_analyst()` always:

1. Builds the doc above (`sent` initialized `False`).
2. Calls `_send()`, whose return value sets `sent`. Under `log`, `_send()` writes an `[ALERT] would
   notify ...` line and **returns `False` — nothing is emailed**.
3. Inserts the doc into the Mongo `notifications` collection (best-effort; skipped/no-op without Mongo
   — see [DATABASE.md](DATABASE.md)).
4. Appends it to the in-memory `NOTIFICATIONS` list.

Together with the `system_event` audit row from the caller, an escalation lands in **three** places:
the `notifications` collection, the in-memory list, and the audit log. None of them sends mail.

`_send()` is the **single pluggable seam**. Today it handles `log` (record only); `smtp`/`api` are
recognized but unimplemented — they log a warning and are treated as not-sent. Swap real dispatch in
here later without touching the decision tree or the ingest pipeline.

## Persistence & startup

Mongo is the source of truth; `NOTIFICATIONS` is a read cache (stored newest-last, served newest-first).
At startup `load_from_mongo()` clears the list and repopulates it from the collection, so prior alerts
survive a restart when Atlas is connected. With no Mongo configured the alert lives only in memory for
the session.

## Config

| Env var | Default | Meaning |
| --- | --- | --- |
| `FRAUD_ANALYST_EMAIL` | `fraud-analyst@example.com` | recipient on every alert's `to` field |
| `NOTIFY_TRANSPORT`    | `log` | `log` = record only; `smtp`/`api` are stubs |

Both are optional (`api/config.py`); defaults make the feature work with zero setup.

## Endpoint

### `GET /notifications`

Returns the alert queue, newest first, with Mongo's `_id` stripped:

```json
{ "count": 2, "results": [ { "notification_id": "ntf_a1b2c3d4", "transaction_id": "tx_live_…",
  "action": "escalate", "score": 0.91, "transport": "log", "sent": false, "…": "…" } ] }
```

Backed by the in-memory cache — no Atlas round-trip per call. See [API.md](API.md) for the full
endpoint set and [DECISION_TREE.md](DECISION_TREE.md) for the routing that decides what lands here.
