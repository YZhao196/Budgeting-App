# Hands-on UI/UX critique — round 2

Produced by driving the running app on-screen (the source `python main.py` build, not the
stale `dist/Budget.exe`) after the round-1 fixes landed: adding/editing/deleting a real
ledger item, setting real budgets, opening the new account dialog, running search, and
visiting every page. Each finding is something observed live, with the root cause traced in
code and concrete solution steps.

**Round-1 fixes confirmed live:** EDIT button gone + `⋯`→"Clear all" menu; Analytics budget
empty state + `BudgetDialog`; Subscriptions legends + hover tooltips; Goals projections
collapsed behind "▸ show projection"; Goals 578 % bar solid green; Settings "Net worth
accounts" card; masked Basiq key; search single-click navigation. See
`docs/hands-on-ux-critique.md`.

Three of the findings below (#1, #2, and the retraction in #2) are **gaps in round 1's own
changes**.

---

## 1. The Overview budget widget is a second, unfixed copy of the all-red bug — ✅ FIXED

**Observed:** The Overview right rail has its own "Budget vs actual — top 5" card rendering
every category as a red overrun (`Rent $2,000 / $0`, `Electric $150 / $0`, …). Round 1 only
fixed the Analytics copy. Worse: after setting real budgets in Analytics (Rent $2,500,
Electric $200, Water $80), the Overview rail **still showed `/ $0`** — navigating away and
back did not help.

**Cause (two independent defects):**

- *Never refreshes.* `_AnalyticsOverview.__init__` (`main.py:379`) is the **only** page class
  that takes no `on_change` callback — it's constructed without one at `main.py:898`. So
  `_edit_budgets` (the "Set budgets…" handler added in round 1) can only call
  `self.set_context(...)`, refreshing itself. It can never reach
  `MainWindow._data_changed` (`main.py:2996`), which is what calls `_load_anchor()` →
  `overview.set_month()` → `_refresh_budget_mini()`. Compounding it, `OverviewPage` (97–237)
  has **no `set_context`**, so `go("overview")` (`main.py:2869`) skips it on navigation.
- *No empty state.* `OverviewPage._refresh_budget_mini` (`main.py:158-167`) filters rows with
  `if r["ideal"] or r["actual"]`. With no budgets set, rows still qualify on `actual`, each
  with `ideal == 0` → every bar a 100 %-overrun red. The Analytics card got an empty state in
  round 1; this one never did.

**Solution steps:**

1. Add an `on_change` parameter to `_AnalyticsOverview.__init__` (`main.py:379`) and store it
   as `self._on_change = on_change`, matching every other page class.
2. Pass it at `main.py:898`: `_AnalyticsOverview(manager, doc, year, month, self._changed)`.
3. In `_AnalyticsOverview._edit_budgets`, after the `set_ideal` loop, call `self._on_change()`
   instead of `self.set_context(...)` — that routes through `MainWindow._data_changed` and
   refreshes the Overview rail *and* the Analytics card in one pass.
4. In `_refresh_budget_mini` (`main.py:162-165`), change the filter to `if r["ideal"]` only.
   The card already does `setVisible(bool(rows))` with `retain_size`, so with no budgets set
   it hides cleanly instead of rendering red. Optionally add a one-line hint pointing at
   Analytics → "Set budgets…".

**Verify:** With no ideals, the Overview rail card is hidden (not red). Set a budget in
Analytics → the Overview rail reflects it immediately, without a restart.

**Status:** Both steps applied — `main.py:164` now filters `if r["ideal"]` only, and
`_AnalyticsOverview` takes `on_change` (`main.py:379`, wired at `main.py:902`) so
`_edit_budgets` (`main.py:792`) calls it instead of only refreshing itself. Verified headless:
with no ideals the rail is hidden; setting an ideal via the same `_on_change()` path
`_edit_budgets` uses makes the rail appear without restarting or renavigating. 114 tests still
pass.

---

## 2. The Add-account dialog opens off-screen — ✅ FIXED

**Observed:** Clicking "+ Add account" (top-right of the Settings accounts card) spawned the
dialog clipped past the **right edge of the screen** — the Name input and the helper text were
cut off, and the Cancel button was unreachable. I had to drag it back on-screen by its title
bar to close it.

**Cause:** `AccountDialog.create`/`edit` (`widgets.py:2210-2219`) call `dlg.move(QCursor.pos())`.
The trigger button sits in the far-right corner, so the dialog's top-left lands within its own
width of the screen edge. The same pattern is used by `PersonDialog` (`widgets.py:2123/2131`),
`GoalDialog` (`widgets.py:4739/4748`) and others — all launched from right-edge "+ Add …"
buttons, so all are exposed.

**Retraction — "Escape doesn't close the dialog" is NOT a bug.** During the live session two
Escape presses appeared to leave the dialog open, and I logged it as a separate defect. A
headless check disproves it:

```python
QTest.keyClick(dlg, Qt.Key.Key_Escape)   # AccountDialog: visible after Escape = False
                                          # BudgetDialog:  visible after Escape = False
```

Escape closes both (Cancel is wired to `self.reject` at `widgets.py:2194`, and QDialog rejects
on Escape by default). The on-screen symptom was the off-screen placement preventing the
synthetic keystroke from reaching the dialog — a symptom of this finding, not its own bug.

**Solution steps:**

1. Add one shared placement helper in `widgets.py` that clamps to the screen's *available*
   geometry:
   ```python
   def place_near_cursor(dlg):
       dlg.adjustSize()
       scr = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
       a = scr.availableGeometry()
       g = dlg.frameGeometry()
       g.moveTopLeft(QCursor.pos())
       g.moveLeft(max(a.left(), min(g.left(), a.right() - g.width())))
       g.moveTop(max(a.top(), min(g.top(), a.bottom() - g.height())))
       dlg.move(g.topLeft())
   ```
2. Replace every `dlg.move(QCursor.pos())` with `place_near_cursor(dlg)` —
   `AccountDialog`, `PersonDialog`, `GoalDialog`, and any other `.create()/.edit()` pair.
3. `adjustSize()` before measuring matters: an unshown dialog reports a stale size hint and the
   clamp would use the wrong width.

**Verify:** Maximize the window, click "+ Add account" in the top-right → the dialog is fully
on-screen with Cancel clickable. Repeat for "+ Add goal" and the People tab's add-person.

**Status:** `place_near_cursor()` added (`widgets.py:49`), and all 10 `dlg.move(QCursor.pos())`
call sites replaced with it — `RepeatDialog`, `TagDialog`, `NoteDialog`, `PersonDialog` (×2),
`AccountDialog` (×2), `BudgetDialog`, `SharedPlanDialog` (×2). (`GoalDialog` was checked and
turned out not to call `move(QCursor.pos())` at all — it centers on its parent by default, so
it was never exposed to this bug; left unchanged.) Verified headless: with the cursor forced to
the extreme bottom-right corner of an 800×800 screen, `AccountDialog`'s resulting frame
geometry is fully contained within the screen's available geometry.

---

## 3. Money spinboxes don't select-on-focus — silent wrong values — ✅ FIXED

**Observed:** In `BudgetDialog`, clicking into a field showing `$0.00` and typing `200`
produced **`$0.20`**, silently. Only `Ctrl+A` first gave `$200`. In a budgeting app a
mistyped budget is a wrong number the user may never notice.

**Cause:** `QDoubleSpinBox` keeps its current text and inserts at the caret. With a `$` prefix
and a pre-filled `0.00`, a click lands the caret mid-number and typed digits splice into the
decimals rather than replacing the value. Nothing selects the existing text on focus.

**Solution steps:**

1. Add a small subclass in `widgets.py` and use it wherever money is entered:
   ```python
   class MoneySpin(QDoubleSpinBox):
       def focusInEvent(self, e):
           super().focusInEvent(e)
           # defer: Qt sets its own selection during focusIn
           QTimer.singleShot(0, self.selectAll)
   ```
2. Swap `QDoubleSpinBox` → `MoneySpin` in `BudgetDialog` (the per-category rows),
   `AccountDialog` (Balance), `GoalDialog`, and the Goals "Edit monthly targets" fields.

**Verify:** Click into the middle of a `$0.00` budget field, type `200`, Tab out → `$200.00`.

**Status:** `MoneySpin` added (`widgets.py:63`). Swapped in for every money `QDoubleSpinBox`:
`AccountDialog.balance`, `BudgetDialog`'s per-category spins, `GoalDialog.target`/`.saved`,
the Goals "Edit monthly targets" fields (`main.py`'s shared `_spin()` helper), the
`SharedPlanDialog` amount + per-member share fields. (The ledger's inline amount editor
(`InlineEdit`, `widgets.py:730`) was checked and already calls `selectAll()` on focus — it's a
`QLineEdit`, not a spinbox, so it was never exposed to this bug.) Verified headless: a plain
`QDoubleSpinBox` receiving typed `"200"` into a focused `$0.00` field yields `$2000.00`
(splice); `MoneySpin` yields `$200.00` (replace).

---

## 4. New items are recurring by default, so their *first* edit fires the scope modal — ✅ FIXED

**Observed:** "+ Add item" → typed "Freelance" → entered the amount → immediately hit
*"'Freelance' repeats. Apply this change to: This occurrence / This + future / All
occurrences."* Deleting the same fresh item fired *"Which occurrences do you want to remove?
This only / This + future / All instances."*

**Why this is wrong:** a brand-new item has exactly **one** occurrence. The question is
unanswerable — all three options are the same thing — so it's pure friction on the most common
workflow (add a thing, give it a number). It also blocks silently: the modal is centred while
the ledger is on the left, and until it's answered the amount simply never commits and the
total never moves.

**Not a contradiction of the round-1 decision.** `docs/hands-on-ux-critique.md` #3 kept the
3-way prompt *by decision* — that's about editing an **established** series, where the choice
is real. This is about the prompt firing on **creation**, where it isn't.

**Solution steps:**

1. In `LedgerCard`/`CategoryRow`, find `_ask_edit_scope` / `_ask_recurring_scope`.
2. Short-circuit before showing the dialog: if the definition has ≤ 1 materialized occurrence
   (or its `range_start` is the current period), apply the change directly and return the
   "all" scope without prompting.
3. Leave the prompt untouched for definitions with a real history — the kept behaviour.

**Status:** Added `ItemStore.is_first_occurrence(def_id, occ_iso)` (`datamanagement.py:682`) —
true when `occ_iso` equals the definition's `start` (its very first possible occurrence, set at
creation by `add_top`/`add_child`). `LedgerCard._resolve_scope` (`widgets.py`) now returns
`"all"` directly when this holds, skipping `_ask_edit_scope`; `_delete` treats the item as
non-recurring (a plain Yes/No "Delete X?" confirm) under the same condition. Verified headless
end-to-end: a definition created via `store.add_top` returns `is_first_occurrence == True` for
its current-month occurrence and `_resolve_scope` returns `"all"` without invoking the dialog
(no hang); the same definition's occurrence in a *later* month still returns `False`, so the
prompt correctly still fires once an item has real history.

**Verify:** Add an item and set its amount → commits silently, total updates immediately.
Edit the amount of an existing recurring item (Rent) → the 3-way prompt still appears.

---

## 5. Tab from a new item's name doesn't reach the amount — ✅ FIXED

**Observed:** After "+ Add item", the name is pre-selected for typing, but Tab commits the name
and drops focus — the amount stays `$0` with no caret. You must click the amount separately, so
adding an item is never a pure keyboard action.

**Solution steps:** On a Tab commit of the name editor, open the amount inline editor for the
same row and `selectAll()` its text (pairs naturally with `MoneySpin` from #3).

**Verify:** "+ Add item" → type name → Tab → type amount → Enter, without touching the mouse.

**Status:** `InlineEdit` (`widgets.py:730`) takes an optional `on_tab` callback and overrides
`focusNextPrevChild` to intercept forward-Tab specifically, so it can commit-and-advance instead
of just losing focus. The name editor's `on_tab` (wired in `CategoryRow`, `widgets.py:865`,
leaf rows only) calls `LedgerCard._commit(node, "name", v, advance_to="amount")`; `_commit`
(`widgets.py:1299`) now takes an `advance_to` param that sets `self._editing` to the next field
instead of `None`. `InlineEdit._grab` already focuses + `selectAll()`s whatever field opens, so
the amount editor comes up pre-selected for free. Verified headless end-to-end: "+ Add item" →
type "Freelance" → simulate Tab → the amount `InlineEdit` has focus with its `"0"` fully
selected → typing `"450"` replaces it cleanly — the full flow works with no mouse click.

---

## 6. Search doesn't highlight or scroll to the item it navigated to — ✅ FIXED

**Observed:** Single-click on a result (the round-1 fix) correctly jumped to Overview for
"Rent", but nothing on the destination page calls out the row — on a busy ledger you still
hunt by eye.

Previously documented as deliberately deferred (`docs/hands-on-ux-critique.md` #2,
`docs/people-pipeline-and-efficiency.md` §4) as needing a focus-id threaded through
`_on_pick`/`MainWindow.go` plus per-page scroll-to support — implemented that for the two
result kinds that map onto a concrete row (Income/Expense ledger items, Accounts).

**Bonus find while implementing this:** `backend.search()` tagged every Account result with
`target="networth"` — a page key that has never existed in `MainWindow.pages` (the real page is
`"settings"`). `_search_pick` silently no-ops when `target not in self.pages`, so **clicking any
Account search result did nothing at all**, with no error. Fixed alongside #6 since threading an
`id` through the same result dicts touched this exact code path.

**Status:**
- `backend.search()` (`backend.py:747, 761`) now includes `"id"` on Income/Expense/Subscription
  and Account results, and Account's `target` is corrected to `"settings"`.
- `widgets.py`: added `flash_widget(widget, revert_style, duration_ms)` — a shared helper that
  tints a widget amber (`T.AMBER` at low alpha) then reverts after ~1.5s. Added
  `LedgerCard.flash_row(node_id)` (`widgets.py:1233`): finds the row by id, auto-expanding a
  collapsed parent first if the target is a hidden child, scrolls it into view via the card's
  own `BoundedScroll`, and flashes it.
- `main.py`: `SettingsPage._account_row` now builds a `QWidget` (was a bare `QHBoxLayout`) so
  individual account rows are addressable; `_refresh_accounts` keeps an id→widget map;
  `flash_account(acct_id)` scrolls/flashes the matching row (the scroll area reference — never
  stored before — is now kept as `self._scroll`). `MainWindow._search_pick` now calls
  `card.flash_row(rid)` for Income/Expense results and `self.settings.flash_account(rid)` for
  Account results.
- Person and Transaction results still don't get a flash (People/Settings don't render either
  as an addressable per-row widget the same way) — left as further-out scope, same reasoning as
  the original deferral, just narrower now.

**Verify:** Search "rent" → single-click → Overview scrolls to and flashes Rent's row amber for
~1.5s. Search "anz" → single-click → **now actually navigates** (previously did nothing) →
Settings scrolls to and flashes the ANZ Plus account row.

**Aside — a real data mishap surfaced while verifying this fix:** running verification scripts
against the live `data/items.json` (rather than an isolated fixture) had, over the course of
this session's testing, reduced it to a handful of leftover test items — the original demo
dataset (Rent, accounts, people, settings) was gone. `data/goals.json` is a separate file and
was untouched. Per the user's direction, the demo dataset was rebuilt via the real `ItemStore`
API (`create_subscription`/`create_shared_plan`/`add_account`/`add_rule`, plus direct `item()`
construction for the plain income/expense items) and cross-checked against every number
observed on-screen earlier in this session — Incoming $5,880 (Employment $5,300 + Resale
[eBay $250 + Marketplace $150] + Dividends $180), Outgoing $2,410.99, Net worth -$210,750,
Spotify Family's $9/$27 split with Sam/Alex each owing $9 — all now match exactly. One
acknowledged simplification: month-to-month historical variation (the different P&L figures
per month in History/Analytics) was not reconstructed — every month now shows the same
flat total, since recreating exact historical per-occurrence overrides for 7 months wasn't
judged worth the effort for demo data. `data/months/*.json` was confirmed to be an unused
legacy artifact (the app derives everything from the flat `items.json`), so it didn't need
touching.

---

## 7. Sidebar module label is hard-truncated to "Quick sta" — ✅ FIXED

**Observed:** The module page titles itself "Quick stats"; the sidebar shows `Quick sta` — no
ellipsis, no tooltip, so the real name is undiscoverable. Any user module with a title longer
than 9 characters truncates the same way.

**Cause:** `main.py:2851` — `self.sidebar.add_module_nav(key, mp["icon"], mp["title"][:9])`.

**Solution steps:** Keep the slice for layout, but signal it and make the full name reachable:
pass `title[:9] + "…"` when `len(title) > 9`, and `setToolTip(full_title)` on the resulting nav
button. (Previously raised as `docs/critique-and-stock-plan.md` #2; still open.)

**Verify:** A module titled "Quick stats" renders `Quick sta…` and hovering shows the full name.

**Status:** Implemented as specified at `main.py:2860` — titles ≤ 9 chars are unchanged; longer
ones render as `title[:9] + "…"` with `setToolTip(full_title)` on the nav button. Verified
headless: the "Quick stats" module's sidebar button reports `toolTip() == "Quick stats"`.

---

## 8. Every goal projects at the same rate — ✅ FIXED (minimal/honest option)

**Observed:** All three goals show an identical **"avg +$3,311/mo"**, and near-identical "on
track by" dates — because each goal is projected using the *total* monthly savings rate,
independently. That implies $3,311/mo flows into Emergency fund *and* New laptop *and*
Vacation simultaneously, which overstates how fast any of them actually completes.

**Solution steps (pick one):**

- *Minimal / honest:* relabel so the assumption is explicit — e.g. "if all savings went here:
  ~2 mo" — leaving the maths alone.
- *Fuller:* divide the savings rate across active goals (evenly, or weighted by remaining
  amount / an explicit per-goal monthly contribution) before projecting, so the dates are
  simultaneously achievable.

**Verify:** With 3 goals and one savings rate, the projected completion dates are consistent
with a plan a user could actually execute — or the caption states the assumption outright.

**Status:** Took the minimal/honest option — the maths was already correct for **linked**
goals (`GoalsPage._goal_row`, `main.py:1105`, sums only that goal's linked expenses); the
identical captions only happened for **unlinked** goals falling back to the shared `avg_pnl`,
which was true for all 3 demo goals. Changed the caption lead only for that unlinked case, from
"on track by {date}" to "if all savings went here, by {date}" (`main.py:1108-1117`), making the
shared-rate assumption explicit instead of implying per-goal pacing. Linked goals keep the
original "on track by" wording since their pacing genuinely is goal-specific. No change to
`goal_eta`/the underlying maths. Verified headless: all three demo goals now render "if all
savings went here, by Sep/Aug 2026 · ~N mo (avg +$3,311/mo)".

---

## 9. Minor

- **Sparse pages.** Goals, History and Quick stats now leave large empty regions below their
  content — collapsing the goal charts (round 1 #8) fixed the scroll but left the page
  bottom-heavy with whitespace. Worth reconsidering what earns the space.
- **One-item overflow menu.** The ledger `⋯` menu holds a single entry ("Clear all…"). Fine,
  but a one-item menu is a slightly odd affordance; revisit if nothing else joins it.

---

## Status

**All 8 numbered findings are fixed and verified** (114 tests pass throughout; each fix has a
headless verification recorded in its section above):

- #1 Overview budget widget — empty-state filter + `on_change` wiring.
- #2 Dialog off-screen placement — shared `place_near_cursor()` clamp, applied to all 10
  affected dialogs.
- #3 Money-field select-on-focus — `MoneySpin`, applied to every money spinbox.
- #4 Recurring-scope prompt firing on creation — `ItemStore.is_first_occurrence`.
- #5 Tab-to-amount flow on new items — `InlineEdit.on_tab` + `_commit(advance_to=...)`.
- #6 Search result highlight/scroll-to — `flash_widget()` + `LedgerCard.flash_row()` +
  `SettingsPage.flash_account()`; also fixed a real silent-no-op bug (Account results pointed
  at a page key, `"networth"`, that never existed).
- #7 Sidebar module label truncation — ellipsis + tooltip.
- #8 Identical goal-projection captions — clarified wording for the shared-rate (unlinked)
  case; linked goals were already correct.

**#9** (sparse pages, one-item overflow menu) is judgement/taste, not a defect — left for a
future design pass rather than a targeted fix.

**Unplanned side effect, since resolved:** implementing #6's verification surfaced that this
session's own test scripts had emptied the live `data/items.json` demo dataset. Rebuilt per the
user's direction and cross-checked against every on-screen figure from this session — see #6's
"Aside" note above for the full account.
