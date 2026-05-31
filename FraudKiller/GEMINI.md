# GEMINI — the AI integration

Gemini is **optional and additive**. It does exactly two jobs, both of which fall back cleanly to
pure rules when no key is present:

1. **Reviewer summaries** — a 1–2 sentence plain-language risk narrative shown in the UI AI panel.
2. **Decision-tree tie-breaker** — a `classify()` verdict consulted *only* on the borderline branch
   of the routing tree (see [DECISION_TREE.md](DECISION_TREE.md)).

All Gemini code lives in `api/gemini.py` (the `detector/` stays web-free and network-free). It uses
the **`google-genai`** SDK and is **lazy** — no client is constructed and no call is made until a
reviewer opens a flag or a borderline transaction is ingested.

---

## Config

From `api/config.py` (env via `python-dotenv`; copy `.env.example` → `.env`). See
[CONFIG.md](CONFIG.md) for the full table.

| Var | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | *(unset)* | Enables Gemini. Empty/missing → AI disabled. |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Model passed to every call. |

`config.gemini_enabled()` is the single gate — it returns `True` only when a key is set. Everything
downstream checks it (or just calls the functions, which return `None` when disabled).

---

## The two functions (`api/gemini.py`)

### `summarize(record) -> str | None`
Builds a short prompt from the scored record — score, label, the ranked `reasons`, amount vs. the
card's median, country/category/channel context — and asks Gemini for a **1–2 sentence reviewer risk
narrative plus a recommended action** (clear / review / escalate). Plain language, no JSON.

- **Cached per `transaction_id`** — a repeat open is free.
- **Persisted** as the `ai_summary` field on the transaction doc (`update_summary` in
  [DATABASE.md](DATABASE.md)), so the cache survives restarts and rides the contract.
- Returns `None` on no key / SDK missing / call failure.

### `classify(record) -> {risk, confidence, rationale} | None`
A **JSON tie-breaker verdict**. Prompts Gemini to return strict JSON with a `risk` of
`high | medium | low`, a numeric `confidence`, and a one-line `rationale`. The decision tree maps
the `risk` value to a route on the borderline branch — nothing else reads it.

- Called **only** by `ingest.decide()` on the borderline-and-non-critical path — never on every
  transaction.
- Returns `None` on no key / SDK missing / call failure / unparseable JSON.

> Prompts above are paraphrased. The literal strings live in `api/gemini.py`; treat that file as the
> source of truth for wording.

---

## Where each is used

```
GET /transaction/{id}/summary   →  gemini.summarize()   (lazy, cached, persisted as ai_summary)
ingest.decide() borderline path →  gemini.classify()    (tie-breaker → route())
```

### Summary endpoint
`GET /transaction/{id}/summary` → `{ transaction_id, summary, enabled }`.
- On first call it lazily runs `summarize()`, persists the result, and returns it.
- `enabled` mirrors `gemini_enabled()`. When `false`, `summary` is `null` and **the UI hides the AI
  panel** (`AiSummary.tsx`) — no error, no empty box. See [API.md](API.md).

### Decision-tree tie-breaker
The router (`detector/decision_tree.route`) is pure and takes an optional `ai_verdict`. Only the
**borderline band `[0.42, 0.80)` with no critical signal** consults AI:

| `classify()` risk | Route |
|---|---|
| `high` | ESCALATE + notify |
| `low` | QUEUE |
| `medium` / `none` / fallback | QUEUE (default to human review) |

`ingest.decide()` calls `classify()` then `route(...)`; every other branch (critical signal,
score ≥ 0.80, score < 0.42) is decided by rules alone and never touches Gemini. `Decision.used_ai`
records whether the verdict was actually consulted. Full branch order in
[DECISION_TREE.md](DECISION_TREE.md).

---

## Graceful fallback

There is no hard dependency on Gemini. When the key is absent, the SDK is missing, or a call throws:

- `summarize()` and `classify()` both return `None`.
- `decide()` routes on **rules only** (borderline → QUEUE by default).
- The summary endpoint returns `enabled: false` and the **UI hides the AI panel**.

This is why the test suite is hermetic — `tests/test_gemini_fallback.py` asserts `None` with no key,
and all 29 tests run with **no secrets** (see [TESTING.md](TESTING.md)).

---

## Cost & quota

Calls are deliberately rare:

- **Summaries are lazy + cached + persisted** — Gemini is hit at most once per transaction, and only
  when a reviewer actually opens that flag. Browsing the queue costs nothing.
- **`classify()` runs only on the borderline branch** of ingest — most transactions auto-clear,
  escalate, or queue on rules and never call out.

So Gemini usage scales with *reviewer attention* and *borderline ingest volume*, not with the size
of the dataset or the request rate on `/transactions`.
