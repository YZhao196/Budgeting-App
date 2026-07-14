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

### 2. Search opens results, but only via Enter/double-click, and with no highlight
**Correction (re-verified live):** My first pass called search a "dead end" — that was
wrong. `SearchDialog` (`widgets.py`) *does* wire `returnPressed → _activate_first` and
`itemActivated → _pick → _on_pick`, and pressing Enter on the "netflix" result **did** jump
to the Subscriptions page. My earlier double-click simply missed the row. So this is not a
bug — search navigation works.

**Remaining friction (minor):** (a) **single-click** only selects, with no hint that Enter or
double-click is how you open — a first-timer may think it's inert; (b) landing on the target
page does **not** highlight or scroll to the found item, so on a busy page you still have to
find it by eye.

**Optional polish (not a fix):** treat single-click as activation for this small result
list, and thread the item id through `_on_pick`/`MainWindow.go` so the destination page can
scroll-to and flash the row. The fuller filtered-search upgrade is in
`docs/people-pipeline-and-efficiency.md` §4.

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

### 4. Top-right EDIT button implies a mode that doesn't exist
**Observed:** Toggling EDIT only reveals a small "Clear all" link under each ledger;
everything else (add, rename, amount, delete ✕) is already editable without it. Its one real
effect is surfacing a *destructive* action, which is the opposite of what "EDIT" suggests.

**Cause:** `TopBar.edit_btn` → `MainWindow._set_edit_mode` → `LedgerCard.set_edit_mode`;
`edit_mode` is read in exactly one place (`widgets.py`, the "Clear all" link). It also resets
on every page change and applies to only 2 of 6 pages.

**Fix (recommended):** Remove the button entirely and move "Clear all" into each ledger
card's own header as a `⋯` overflow menu item behind a confirm dialog. (Full analysis and two
alternative options in `docs/people-pipeline-and-efficiency.md` §2.)

### 5. Analytics "Budget vs actual" is all-red by default
**Observed:** Every category shows `$2,000 / $0` — the "ideal" budget is $0, so every bar is
a red overrun. There's no obvious affordance on that screen to *set* a category budget, so
the flagship budget chart reads as "everything is over budget" out of the box.

**Cause:** `budget_report` uses each category's `ideal`, which is unset (0) for demo/new data;
the ideal is only editable elsewhere (the ledger detail), not discoverable from Analytics.

**Fix:** When no ideals are set, show an empty/onboarding state on the budget card ("Set
category budgets to track pace →") instead of rendering every bar as a red overrun; and add a
direct affordance to set a category's ideal from the budget row itself (click the `/ $0` to
edit).

### 6. Subscriptions visuals have no legend
**Observed:** The month calendar shows green/amber dots and the "Renewal timeline" shows
three colored circles, with nothing explaining what the colours or dots mean. You hover and
guess.

**Cause:** `CalendarHeatmap` and `SubscriptionTimeline` (`widgets.py`) encode
spend/due/income and per-subscription identity in colour with no rendered key.

**Fix:** Add a one-line legend under each: for the calendar, "● due  ● income  shaded =
spend"; for the timeline, either a small colour key or label each marker. Also consider
merging the calendar and timeline — they answer the same "when does it renew" question twice.

### 7. Settings has no account management, and the API key is unmasked
**Observed:** Net worth and the forecast depend on accounts, but Settings only offers
currency, CSV import, categorisation rules, and Basiq sync — no add/edit account anywhere.
Accounts can currently only be changed by hand-editing `data/items.json`. Separately, the
Basiq **API-key field is plain text**, unmasked, directly under the bank-connection section.

**Cause:** `datamanagement.py` has `add_account`/`update_account`/`remove_account` but nothing
in `main.py` calls them; the API-key `QLineEdit` in `SettingsPage` has no `echoMode` set.

**Fix:** Add a "Net worth accounts" card to `SettingsPage` (list accounts, "+ Add account"
via an `AccountDialog` following the existing `PersonDialog` static `.create()/.edit()`
pattern, rows wired to `update_account`/`remove_account`). Set
`key_field.setEchoMode(QLineEdit.EchoMode.Password)` on the Basiq key input. (This accounts
card is also the prerequisite for the stock/holdings feature in
`docs/critique-and-stock-plan.md`.)

### 8. Goals projection charts are a lot of scroll for little signal
**Observed:** Three near-flat, full-width line charts (one per goal) restate what the
one-line caption already says ("on track by Sep 2026, ~2 mo").

**Cause:** `GoalsPage._goal_row` (`main.py`) always renders a full `LineChart` per goal.

**Fix:** Collapse each goal's projection chart by default behind an expandable header
(`Clickable` toggling the chart's visibility); the caption carries the "am I on track"
answer, the chart is opt-in detail.

---

## Minor

### 9. Window doesn't remember size/position, opens behind other windows
**Observed:** The app opened behind File Explorer and doesn't restore its previous
size/position or maximized state between launches.

**Fix:** Persist `geometry()`/`saveState()` to `settings` on close and restore on launch;
raise/activate the window on startup.

---

## What's genuinely good (keep)

- Inline name/amount editing on ledger rows is smooth.
- Month/week navigation and the calendar month-picker feel nice and responsive.
- The window-resize fix holds: dragging the window short scrolls the right column (Weekly P&L
  → chart → predicted income all reachable) instead of hiding any section.
- Dense, scannable, consistently on-theme — the terminal/trading-desk feel from PRODUCT.md
  comes through.

---

## Suggested priority order

1. ~~**#1 red winning-bar**~~ — ✅ done (opt-in bounded overrun; Goals bar now green).
2. ~~**#3 recurring scope modal**~~ — decided to keep the 3 options; no change.
3. **#5 all-red budget chart** + **#7 accounts UI / masked key** — make the core budgeting
   and net-worth loops usable without editing JSON.
4. **#4 EDIT button**, **#6 legends**, **#8 collapsed goal charts**, **#2 search polish**,
   **#9 window state** — polish (#2 downgraded: search already navigates on Enter/double-click).
