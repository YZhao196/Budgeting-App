# App critique & stock-tracking plan

Produced by driving the real app (a live `MainWindow`, not a mock) across every page — Overview, Analytics, Goals, History, Subscriptions (+ People tab), Settings — and reading the code paths behind what the screenshots showed.

## Critique

### 1. `ProgressBar` overrun rendering breaks for any value ≥200% of target — Goals page

**File:** `widgets.py` — `ProgressBar.paintEvent`, the overrun block:
```python
if self._raw > 1.0:
    over = min(1.0, self._raw - 1.0)
    oc = QColor(T.RED); oc.setAlpha(200)
    p.setBrush(oc)
    p.drawRect(QRectF(w * (1 - over), 0, w * over, h))
```
`over` is meant to be "how much of the bar's width to cap in red," but it's computed as `self._raw - 1.0` with no normalization — so at `_raw = 5.78` (the real "Progress to target" bar on Goals, July's P&L at 578% of target), `over` clamps to `1.0` and the red rectangle spans `x=0` to `x=w`: **the entire bar renders solid red**, hiding the base fill entirely.

This is worse than a cosmetic glitch: the color passed in at the call site (`main.py`, `GoalsPage.set_context`) is correctly `T.GREEN` when `frac >= 1` — beating your P&L target is good news — but the broken overrun paint overwrites it with red, the app's own "bad/expense" color. A user glancing at the Goals page sees an alarming solid-red bar for what is actually a great month. Confirmed live (screenshot), not just read from source.

**Fix direction:** cap the overrun visually at a small fixed cap (e.g. never more than ~15-20% of bar width) regardless of how large the true overrun is, and only ever tint a portion near the target tick, not from `x=0`. The target tick itself (amber, drawn at `tx = w * self._target`) is also invisible in this specific case because target=1.0 puts it at the bar's right edge, indistinguishable from the border — worth moving fractionally inward (e.g. `tx - 1px` inset) so it's visible even at target=100%.

### 2. Sidebar module nav labels are hard-truncated mid-word, no ellipsis, no tooltip

**File:** `main.py:2690` — `self.sidebar.add_module_nav(key, mp["icon"], mp["title"][:9])`

The demo module (`data/modules/example_quickstats.py:51`) registers itself as `"Quick stats"`; the sidebar renders it as **"Quick sta"** — sliced to exactly 9 characters with no `…` and no `setToolTip` carrying the full name. Confirmed live in the sidebar screenshot. Any user-authored module (the plugin system is explicitly designed for user-dropped Python files) with a title longer than 9 characters will render truncated the same way, silently, with no way to discover the real name short of hovering and finding nothing.

**Fix direction:** either widen the nav column to fit reasonable titles, wrap to two lines, or truncate with a trailing `…` plus `setToolTip(full_title)` so the full name is at least discoverable on hover.

### 3. No UI anywhere to add, edit, or remove accounts

**Files:** `datamanagement.py:806-825` defines `add_account` / `update_account` / `remove_account` on `ItemStore`; `backend.py:795` (`net_worth`) and `backend.py:805` (`liquid_balance`) consume the account list. **None of the three CRUD methods is ever called from `main.py`.** Grepping the whole UI layer for them turns up nothing — the only place accounts surface at all is the read-only "Net worth — history" `AreaChart` on the Analytics page (`main.py:459`, `610`).

Today, the only way to add an account — including the "Shares" investment account already sitting in the demo data at `$9,500` — is to hand-edit `data/items.json`'s `"accounts"` array directly. There is no dialog, no Settings section, nothing reachable from the running app. This is a real functional gap, not a polish issue: net worth, liquid-balance forecasting, and (per the plan below) stock tracking all depend on the account list, and there's currently no way for a user to build or maintain it without leaving the app.

### 4. Minor / lower-priority observations

- **History page** monthly-history bars (`main.py`, `HistoryPage`) show a green fill against a gray track with no axis or scale label — presumably relative to the best month, but that's not stated anywhere on the card. Low priority; the numbers to the right of each bar make it self-correcting on a second look.
- **Settings → Live bank sync** "Basiq API key" field renders as a plain (non-masked) text input. It's the user's own key on their own machine, and the card already discloses "Only your Basiq API key is stored locally" — not a real security bug, but a password-style `echoMode` would be a small trust-signal improvement, especially since the field sits directly under a bank-connection section.
- **Subscriptions → Renewal timeline**: markers are colored per-subscription with no legend connecting color to name beyond hover — fine for 2-3 subscriptions (today's case) but will get harder to parse as the list grows past ~5-6.

## Stock-tracking plan

### Why this is the natural next feature

The account model already has an `"investment"` kind (`LIABILITY_KINDS`/`LIQUID_KINDS` in `backend.py:791-792` implicitly treat anything not cash/savings/debt/credit as a non-liquid asset) and the demo data already carries one: `{"name": "Shares", "kind": "investment", "balance": 9500.0}`. Today that's a single opaque number a user has to update by hand whenever the market moves. The natural next step is to let that number be *derived* — from real holdings (ticker + share count) instead of typed in — while changing nothing about how `net_worth()`/`liquid_balance()`/the net-worth chart consume the account list.

### Design goals

- **Don't break the existing account model.** An investment account's `balance` field stays authoritative for every consumer that doesn't know about stocks (net worth, liquid balance, the area chart) — it just becomes *computed* instead of *typed* when holdings are attached, rather than replaced by a new parallel system.
- **Offline-first, matching the app's own stated posture.** `bank_sync.py`'s docstring and the Settings page both stress "your bank login is never entered into this app" / "stored locally." A live stock-price feature needs an equivalent story: prices come from a fetch the user explicitly triggers (not a background poller phoning home constantly), and the app must work fine with stale or no prices (manual entry fallback).
- **Reuse the existing dialog/CRUD patterns.** The app already has a consistent pattern for this (e.g. `PersonDialog` in `widgets.py`, `SharedPlanDialog`, `GoalDialog`) — a themed `QDialog` with a static `.create()`/`.edit()` pair, wired through an `ItemStore` method, refreshed via `on_change`. Stock holdings should follow the exact same shape, not invent a new one.

### Data model

Extend the account record (`datamanagement.py:87`, `account()`) with an optional `holdings` list, only present on `kind="investment"` accounts:

```python
{
  "id": ..., "name": "Shares", "kind": "investment",
  "balance": 9500.0,          # stays authoritative; recomputed from holdings when present
  "holdings": [
    {"id": ..., "symbol": "VAS.AX", "shares": 120.0, "cost_basis": 62.10,
     "last_price": 79.15, "last_price_at": "2026-07-13T09:00:00"}
  ]
}
```

- `cost_basis` (average price paid) enables a gain/loss figure without needing full lot-level tracking — matches the app's existing "enough detail to trust the number, not exhaustive" posture (see `PRODUCT.md`'s density principle).
- `last_price`/`last_price_at` are cached locally so the account balance is always computable offline; a manual "Refresh prices" action updates them, nothing runs automatically in the background.
- An investment account with an empty `holdings` list behaves exactly as today — a plain typed balance — so existing data (and the demo "Shares" account) doesn't need migration on day one.

### Backend (`backend.py`, `datamanagement.py`) — pure, unit-tested, no Qt

- `datamanagement.py`: `add_holding(account_id, symbol, shares, cost_basis)`, `update_holding(...)`, `remove_holding(...)` — same shape as the existing `add_account`/`update_account`/`remove_account`.
- `backend.py`: `holding_value(holding) -> float` (`shares * last_price`, falling back to `cost_basis` if no price cached yet — never `None`/crash); `account_value_from_holdings(account) -> float` (sum of `holding_value` across an account's holdings); `portfolio_gain(account) -> dict` (`{cost, value, gain, gain_pct}` per account, for a gain/loss readout).
- **`net_worth()` and `liquid_balance()` in `backend.py` do not change.** The recompute step (below) keeps `account["balance"]` in sync with holdings *before* those functions ever run, so every existing consumer keeps working untouched.
- A `refresh_prices(store, fetch_fn)` orchestration function that: iterates investment accounts with holdings, calls `fetch_fn(symbol)` for each distinct symbol (deduped), writes `last_price`/`last_price_at`, recomputes `account["balance"] = sum(holding_value(...))`, and persists via `store.save()`. `fetch_fn` is injected so the pure backend stays testable without a network call in `tests/`.

### Price source

A local price fetch, not a bundled paid API dependency — matching the existing `bank_sync.py` pattern (optional, user-supplied credentials, explicit opt-in, "beta" labeled). Concretely: a small `stock_prices.py` module wrapping a free/delayed-quote endpoint (e.g. Yahoo Finance's unauthenticated quote endpoint, already widely used for exactly this without an API key) behind the same `fetch_fn(symbol) -> float | None` seam, so it's swappable later without touching `backend.py`. Network errors return `None` per-symbol rather than raising, so one bad ticker doesn't block refreshing the rest of the portfolio.

### UI

- **New `HoldingDialog`** (`widgets.py`), following `PersonDialog`'s exact shape: Symbol, Shares, Cost basis fields, `.create()`/`.edit()` static methods.
- **Extend the (currently nonexistent) account management surface.** Since finding #3 above means there's no accounts UI at all today, this plan includes building the minimal version: a "Net worth accounts" card on the Settings page (next to the existing "Connect bank accounts" card, which is the closest existing analog) listing accounts with an "+ Add account" action (`AccountDialog`, same pattern), and for `kind="investment"` accounts specifically, a "Holdings" sub-list with "+ Add holding" and a "Refresh prices" button that calls `refresh_prices`.
- **Net worth chart annotation.** On the Analytics "Net worth — history" card, add a small per-account breakdown on hover (the `AreaChart` already tracks assets vs. liabilities; extending the hover pill to itemize by account, or at least call out the investment portion, makes the derived number legible rather than a single opaque total).
- **Gain/loss readout.** Wherever the investment account's balance is shown (the accounts list, and optionally a compact line in the net-worth card), show `portfolio_gain`'s `gain`/`gain_pct` alongside — reusing the existing green/red functional-color convention (gain ≥0 → `T.GREEN`, else `T.RED`), never as a standalone decorative color.

### Phased build order

1. Data model + backend helpers (`holding_value`, `account_value_from_holdings`, `portfolio_gain`, `add_holding`/`update_holding`/`remove_holding`) — pure, fully unit-testable before any UI exists.
2. Settings → accounts UI (the missing piece from finding #3) — needed regardless of stocks, and stocks has nothing to attach to without it.
3. `HoldingDialog` + wiring into the new accounts UI; manual price entry only (no fetch yet) — ships a usable feature end to end.
4. `stock_prices.py` fetch + `refresh_prices` + a "Refresh prices" button — the live-data layer, addable without touching anything from steps 1-3.
5. Net-worth chart / gain-loss readout polish.

### Verification approach

Same pattern already established in this codebase: `pytest` cases for every new pure `backend.py`/`datamanagement.py` function (holding value math, gain/loss math, recompute-balance-from-holdings, the dedup logic in `refresh_prices`), then a headless `MainWindow` drive (as used throughout this session) to screenshot the new Settings accounts card and the holding dialog, checking the derived balance and gain/loss render correctly against a fixture account with known holdings and a stubbed `fetch_fn`.
