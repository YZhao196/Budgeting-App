# Hands-on UI/UX critique

Produced by driving the running app on-screen like a real user — adding, editing, and
deleting rows; running search; navigating months; resizing the window; and opening the
dialogs on every page. Each finding below is something observed live, with a concrete
proposed fix and the file/function to touch.

---

## Broken / misleading

### 1. Goals "Progress to target" bar is red when you're *winning*  — ✅ FIXED
**Observed:** At 578% of the P&L target the entire "Progress to target" bar renders in the
terracotta/red used everywhere else for expenses and losses. The "578%" number is green but
the bar reads as alarming for what is actually a great month.

**Cause:** `ProgressBar.paintEvent` (`widgets.py`) overrun block computed `over = min(1.0,
self._raw - 1.0)`; at `_raw = 5.78` it clamped to `1.0` and the red rectangle spanned the
full width (`x=0 → w`), painting over the green fill entirely.

**Fix applied:** The red overrun cap is now **opt-in** (`ProgressBar(..., overrun=True)`) —
"past 100 %" is only *bad* for a spend-vs-budget bar; a save-toward-target bar treats
exceeding the target as success and must not be tinted with the loss colour. The Goals
"Progress to target" bar does not opt in, so it now shows a solid green fill (verified live
at 578 %). When `overrun=True` is used, the cap is bounded to ≤15 % of the width so a large
overshoot shows a small red sliver at the end rather than flooding the bar. The amber target
tick is also inset 1px so it stays visible at `target == 1.0`. Verdict confirmed with a
headless Goals grab.

### 2. Search opens results, but only via Enter/double-click, and with no highlight — ✅ PARTIALLY FIXED
**Correction (re-verified live):** My first pass called search a "dead end" — that was
wrong. `SearchDialog` (`widgets.py`) *does* wire `returnPressed → _activate_first` and
`itemActivated → _pick → _on_pick`, and pressing Enter on the "netflix" result **did** jump
to the Subscriptions page. My earlier double-click simply missed the row. So this is not a
bug — search navigation works.

**Fix applied:** `SearchDialog` now activates on a **single click** (`results.itemClicked →
_pick`, in addition to Enter/double-click). A `_picked` guard prevents the click+activate
double-fire on a mouse double-click. Select-then-open friction is gone for this small list.

**Deferred (not done):** highlighting / scrolling-to the found item on the destination page
still isn't wired — it needs a "focus id" threaded through `_on_pick`/`MainWindow.go` and
per-page scroll-to-and-flash support on every target page (a large cross-page change). The
fuller filtered-search upgrade is tracked in `docs/people-pipeline-and-efficiency.md` §4.

### 3. Recurring edit/delete scope modal — KEPT BY DECISION (not changing)
**Observed:** Changing one recurring row's amount pops *"'X' repeats. Apply this change to:
This occurrence / This + future / All occurrences."* Deleting it pops *"Which occurrences do
you want to remove? This only / This + future / All instances."* (`LedgerCard`/`CategoryRow`
route every recurring field commit and delete through `_ask_edit_scope` /
`_ask_recurring_scope`.)

**Decision:** Keep the explicit 3-way prompt as-is. It was considered for a silent-default +
undo treatment to cut friction, but the owner chose to keep the three options on every
recurring edit/delete — the explicitness is deliberate. No change. (Left here as a documented
decision so it isn't re-raised later.)

---

## Confusing affordances

### 4. Top-right EDIT button implies a mode that doesn't exist — ✅ FIXED
**Observed:** Toggling EDIT only reveals a small "Clear all" link under each ledger;
everything else (add, rename, amount, delete ✕) is already editable without it. Its one real
effect is surfacing a *destructive* action, which is the opposite of what "EDIT" suggests.

**Cause:** `TopBar.edit_btn` → `MainWindow._set_edit_mode` → `LedgerCard.set_edit_mode`;
`edit_mode` is read in exactly one place (`widgets.py`, the "Clear all" link). It also resets
on every page change and applies to only 2 of 6 pages.

**Fix applied:** The EDIT button and the whole `edit_mode` mechanism are gone — removed
`TopBar.edit_btn`/`edit_changed`/`_toggle_edit`/`_style_edit_btn`/`reset_edit`,
`LedgerCard.edit_mode`/`set_edit_mode`, and `MainWindow._set_edit_mode` plus its
connect/reset calls in `go()`. "Clear all" now lives in each ledger card's own header as a
`⋯` overflow menu (`_open_overflow` → themed `QMenu` → "Clear all…"), still behind the
existing `_clear_all` confirm dialog. It's always reachable, no mode toggle. Verified live
headless on Overview.

### 5. Analytics "Budget vs actual" is all-red by default — ✅ FIXED
**Observed:** Every category shows `$2,000 / $0` — the "ideal" budget is $0, so every bar is
a red overrun. There's no obvious affordance on that screen to *set* a category budget, so
the flagship budget chart reads as "everything is over budget" out of the box.

**Cause:** `budget_report` uses each category's `ideal`, which is unset (0) for demo/new data;
the ideal is only editable elsewhere (the ledger detail), not discoverable from Analytics.

**Fix applied:** When no ideals are set the budget card now shows an onboarding empty state
("No category budgets set yet — click 'Set budgets…' …") instead of a wall of red bars
(`_AnalyticsOverview` computes `any_ideal` and toggles `self.bva` / `self._bva_empty`). A
"Set budgets…" link in the card header opens a new `BudgetDialog` (a scrollable list of
category rows with a spinbox each); saving writes every ideal via `dm.set_ideal(...)` and
re-renders. Verified live headless on Analytics.

### 6. Subscriptions visuals have no legend — ✅ FIXED
**Observed:** The month calendar shows green/amber dots and the "Renewal timeline" shows
three colored circles, with nothing explaining what the colours or dots mean. You hover and
guess.

**Cause:** `CalendarHeatmap` and `SubscriptionTimeline` (`widgets.py`) encode
spend/due/income and per-subscription identity in colour with no rendered key.

**Fix applied:** Added a `dot_legend(items)` helper (swatch + muted label pairs) and rendered
one under each visual — calendar: "● bill due  ● income  ● spend (shaded)  ● today";
timeline: "● income due  ● subscription due" plus a "Marker size ∝ amount; hover for name &
date" note. Verified live headless on Subscriptions. (Merging the two visuals was considered
but left as-is — they read as complementary month-grid vs. 60-day horizon views.)

### 7. Settings has no account management, and the API key is unmasked — ✅ FIXED
**Observed:** Net worth and the forecast depend on accounts, but Settings only offers
currency, CSV import, categorisation rules, and Basiq sync — no add/edit account anywhere.
Accounts can currently only be changed by hand-editing `data/items.json`. Separately, the
Basiq **API-key field is plain text**, unmasked, directly under the bank-connection section.

**Cause:** `datamanagement.py` has `add_account`/`update_account`/`remove_account` but nothing
in `main.py` calls them; the API-key `QLineEdit` in `SettingsPage` has no `echoMode` set.

**Fix applied:** Added a "Net worth accounts" card to `SettingsPage` — lists every account
(name + kind label + balance in asset/liability colour), a running "Net worth" total, and
edit/remove controls per row, plus "+ Add account". A new `AccountDialog` (Name / Type combo
/ Balance, following the `PersonDialog` static `.create()/.edit()` pattern) is wired through
`add_account`/`update_account`, and remove goes via `remove_account` behind a `QMessageBox`
confirm. The Basiq key input now has `setEchoMode(QLineEdit.EchoMode.Password)`. Verified live
headless on Settings. (This accounts card is also the prerequisite for the stock/holdings
feature in `docs/critique-and-stock-plan.md`.)

### 8. Goals projection charts are a lot of scroll for little signal — ✅ FIXED
**Observed:** Three near-flat, full-width line charts (one per goal) restate what the
one-line caption already says ("on track by Sep 2026, ~2 mo").

**Cause:** `GoalsPage._goal_row` (`main.py`) always renders a full `LineChart` per goal.

**Fix applied:** Each goal's projection `LineChart` now starts `setVisible(False)` behind a
`Clickable("▸ show projection")` toggle that shows/hides it and swaps the label text. The
one-line caption carries the "am I on track" answer; the chart is opt-in detail. Verified live
headless on Goals — the page is now ~3 collapsed rows instead of three full-width charts.

---

## Minor

### 9. Window doesn't remember size/position, opens behind other windows — ✅ FIXED
**Observed:** The app opened behind File Explorer and doesn't restore its previous
size/position or maximized state between launches.

**Fix applied:** `MainWindow.closeEvent` now persists `saveGeometry()` (base64) into
`dm.settings()["window_geometry"]` and saves; `__init__` restores it via `restoreGeometry`
when present. `main()` calls `win.raise_(); win.activateWindow()` after `show()` so the app
comes to the front on launch.

---

## What's genuinely good (keep)

- Inline name/amount editing on ledger rows is smooth.
- Month/week navigation and the calendar month-picker feel nice and responsive.
- The window-resize fix holds: dragging the window short scrolls the right column (Weekly P&L
  → chart → predicted income all reachable) instead of hiding any section.
- Dense, scannable, consistently on-theme — the terminal/trading-desk feel from PRODUCT.md
  comes through.

---

## Status (all addressed)

1. ~~**#1 red winning-bar**~~ — ✅ done (opt-in bounded overrun; Goals bar now green).
2. ~~**#3 recurring scope modal**~~ — decided to keep the 3 options; no change.
3. ~~**#5 all-red budget chart**~~ + ~~**#7 accounts UI / masked key**~~ — ✅ done; the core
   budgeting and net-worth loops are now usable without editing JSON (empty-state + `BudgetDialog`;
   Settings accounts card + `AccountDialog`; masked Basiq key).
4. ~~**#4 EDIT button**~~ (removed; Clear all → card `⋯` menu), ~~**#6 legends**~~,
   ~~**#8 collapsed goal charts**~~, ~~**#9 window state**~~ — ✅ done.
5. **#2 search polish** — ✅ single-click activation added; the destination scroll-to/flash is
   deferred (large cross-page change, tracked in `docs/people-pipeline-and-efficiency.md` §4).

Every finding is either fixed or a documented deliberate decision (#3 kept, #2 highlight
deferred). Verified with `pytest` (114 passing) and headless page grabs of Overview, Analytics,
Subscriptions, Goals, and Settings.
