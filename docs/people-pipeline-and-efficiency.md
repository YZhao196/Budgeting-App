# People pipeline, the EDIT button, fluff audit, and per-page efficiency

Planning notes only — no code changes. Every item below names the concrete files/functions to touch and how, so any of these can be picked up and executed directly.

1. A real person-creation pipeline for subscriptions (kill the "one member per line" text box).
2. Analysis of the top-right **EDIT** button.
3. Fluff that doesn't belong in an in-depth budget tracker — and exactly how to remove each.
4. How every page can be made faster — and exactly how to build each fix.

---

## 1. Fully-fledged person creation pipeline

### The current state (and why it's the weak point)

There are **two disconnected ways** a person enters the system, joined only by string matching:

- **Inside a subscription** (`SharedPlanDialog`, `widgets.py`): a `QPlainTextEdit` labelled "Members (one per line)". You type raw names, or `Name = amount` lines for a custom split. On save these become `shared["members"] = [{"name": "Sam"}, {"name": "Alex", "share": 9.0}]`.
- **On the People tab** (`PersonDialog` + `_build_people` in `main.py`): a proper record `{id, name, email, phone, note}` stored in the app-wide `people` registry, with tick-boxes to assign a person to each shared plan.

**The core defect:** the two are linked *only by name*. `set_person_in_sub` (`datamanagement.py:1150`), `person_in_subs`, `member_shares`, `who_owes`, and `people_roster` all match on `m.get("name") == name`. A member inside a plan carries **no `person_id`** — just a name string. Consequences:

- Rename "Sam" → "Samuel" and it only stays consistent because `update_person` (`datamanagement.py`) manually walks every plan rewriting the string. Miss any path and they desync.
- Two different people literally named "Sam" are indistinguishable and will merge silently.
- A member typed into the `SharedPlanDialog` text box that doesn't exactly match a registry name becomes a **ghost member**: it exists in the plan, drives `who_owes`, but has no profile and won't tick as "in this sub" on the People tab until the strings happen to align.
- Contact details captured on the People tab are invisible everywhere the split actually matters.

So the box is a symptom. The fix is **one canonical person record, referenced everywhere by stable ID.**

### Target model

Person registry entry (extend the existing `people` record):
```json
{ "id": "p_ab12", "name": "Sam Lee", "email": "sam@x.com", "phone": "0400…",
  "note": "housemate", "pay_method": "Beem", "archived": false }
```
Plan member becomes an **ID reference plus per-plan override**:
```json
"members": [ { "person_id": "p_ab12", "share": 9.0 } ]
```
`name` is derived from the registry at read time; `share` stays on the membership because it's plan-specific.

### The pipeline (UX flow)

Replace the free-text members box in `SharedPlanDialog` with a **member picker**:

1. **"Add member" button** opens a popup listing the registry (searchable as it grows), each row a checkbox — multi-select in one gesture. Same pattern the People tab already uses, moved to where the split is defined.
2. **"+ New person" inline** at the top of that popup opens `PersonDialog` (already exists), creates the record, and immediately selects it.
3. Selected members render as **removable chips/rows**, each showing name + (for custom splits) an inline share field. Even split → no per-row field, just the live per-head amount (the hint logic already computes it).
4. **Owner-pays** stays, but its live hint counts real selected members, not parsed text lines.

### Backend / model work

- **Migration** in `ItemStore.load()` next to the existing `_migrate_*` steps: for every `shared.members` entry with a `name` but no `person_id`, resolve-or-create a registry person by name and rewrite to `{person_id, share?}`. Idempotent; a second run is a no-op.
- **Rewrite the join functions** (`member_shares`, `who_owes`, `people_roster`, `person_in_subs`, `set_person_in_sub`, `plan_summary`) to key on `person_id`, looking the name up from the registry. `update_person` stops walking plans — the rename is automatic because the name lives in one place.
- **Per-occurrence `member_paid` overrides** are keyed by name today (`overrides[date].member_paid = {"Sam": true}`); re-key by `person_id` in the same migration.
- **Archive, don't delete.** Add `archived: true` instead of `remove_person` dropping them from every plan, so historical split records survive while the person leaves the pickers.

### Verification

`pytest` for: migration (name-only → id-linked, idempotent), rename propagation (registry rename → roster reflects it with zero plan writes), two-same-name stay distinct, archived person keeps historical `member_paid` but is absent from new pickers. Then a headless `MainWindow` screenshot of the new picker + chip UI.

### Out of scope (tracker, not CRM)

Avatars-as-images, social graph, contact-book import, per-person messaging, payment-provider integration. A free-text "pay method" is the ceiling.

---

## 2. The top-right EDIT button — analysis

### What it actually does (from the code)

`TopBar.edit_btn` (`widgets.py:588`) is a checkable EDIT⇄DONE toggle. Clicking it emits `edit_changed`, which `MainWindow._set_edit_mode` (`main.py:2695`) fans out to exactly four widgets: the Overview income/expense ledger cards and the Analytics income/expense ledger cards, calling `LedgerCard.set_edit_mode(on)`.

Inside `LedgerCard`, `edit_mode` is read in **exactly one place** — `widgets.py:1197`:
```python
if self.edit_mode:
    clr = Clickable("Clear all", …)   # a destructive "delete every row" link
    self.list_box.addWidget(clr)
```
That is the button's entire payload. Everything else a user would call "editing" is **already available in view mode**: the `CategoryRow` docstring (`widgets.py:814`) literally says *"✕ delete always visible; + add-child revealed on hover"*, and add-item, rename, amount edit, tag, note, repeat, and due are all reachable by hover/click regardless of the toggle.

### Why it's a problem

- **It implies a mode that doesn't exist.** A prominent, persistent-looking top-right button labelled EDIT signals "the app is read-only until you click me." But the ledgers are fully editable already. The button teaches a false model.
- **Its only real effect is to surface a destructive action.** The one thing it gates is "Clear all" — wipe every row. So the button's actual meaning is "reveal the nuke button," which is the opposite of what "EDIT" suggests and far more dangerous than its label admits.
- **It only applies to 2 of 6 pages.** It does nothing on Goals, History, Subscriptions, or Settings, yet it sits in the global top bar on every page (a global-looking control with local, mostly-absent effect).
- **It doesn't even persist.** `go()` (`main.py:2713`) calls `reset_edit()` + `_set_edit_mode(False)` on every page change, so the "mode" evaporates the moment you navigate. A mode that resets on navigation isn't a mode.

### What to do about it — three options, in order of preference

1. **Remove it entirely (recommended).** Delete `edit_btn` + `edit_changed` + `reset_edit`/`_style_edit_btn`/`_toggle_edit` from `TopBar`, `_set_edit_mode`/its `go()` calls from `MainWindow`, and `edit_mode`/`set_edit_mode` from `LedgerCard`. Relocate the one thing it gated — "Clear all" — into the ledger card's own header as a small `⋯` overflow menu item with a confirm dialog (destructive actions belong behind a menu + confirm, not a top-bar mode). Net: less chrome, no false mode, the dangerous action is where it belongs and guarded.
2. **Make it real.** If a distinct edit mode is genuinely wanted, make it *earn* the label: in view mode hide the per-row ✕ and drag affordances (calmer read); in edit mode reveal ✕, reordering, multi-select + bulk delete, and "Clear all." Then EDIT means something and the destructive action is scoped to it. More work, only worth it if the ledgers feel too busy at rest.
3. **At minimum, relabel + persist.** If neither of the above, rename it "Clear all…" (say what it does), scope its visibility to Overview/Analytics only via the existing `_NAV_VIS` table, and stop resetting it on navigation. This is the weakest option — it keeps a mode toggle whose only job is one destructive link.

---

## 3. Fluff — what to cut, and exactly how

Principle: an *in-depth* tracker earns density by making the money numbers more trustworthy or faster to maintain. Anything else is fluff.

### Cut

- **User plugin/module system** (`modules.py`, `data/modules/`, `mod:` sidebar entries). Unsandboxed drop-in Python for a single-user tool — large surface, no real need; the one demo module duplicates a native panel.
  - **How:** delete `modules.py` and `data/modules/`; remove `_load_user_modules()` and its call in `MainWindow.__init__`; strip `mod:`-prefix handling from `go()`, the `_NAV_VIS` table, and `sidebar.add_module_nav`; remove the "Modules" status card from `SettingsPage`. Softer variant: keep the code but gate loading behind a `settings["enable_modules"]` flag defaulting `False`, so nothing loads unless explicitly turned on. Verify: app launches, no `mod:` nav item, `pytest` green.

- **"Copy reminder" clipboard button** (People tab). A message composer ("Hi Sam, you owe $9…") bolted onto a tracker; the balance it's built from is already on the card.
  - **How:** in `main.py` `_build_people`, remove the "Copy reminder" `_button(...)` and its `_copy_reminder` connection; delete the `_copy_reminder` method and the `_people_status` label it writes to. `who_owes`/`people_roster` untouched. No test change (pure UI removal).

- **Dead onboarding wizard** (`OnboardingDialog` and the `_go`/`_nav_row` step scaffolding). It's already **not wired up** — `MainWindow.__init__` sets `self._first_run = False  # onboarding deferred` and the store seeds demo data, so this multi-step wizard is dead code carrying maintenance weight.
  - **How:** delete the `OnboardingDialog` class and its `_go`/`_nav_row`/`_p_*` page-builder methods outright (nothing calls them). If a first-run experience is ever wanted, replace with a single "Start empty / Keep demo data" choice on first launch — not a wizard. Verify: grep confirms no references; app still launches.

- **Two near-duplicate P&L charts on Analytics** ("P&L vs target — last 5 months" and "Income vs Expenses — all months") say overlapping things.
  - **How:** collapse into one `LineChart` card with a small `SegTabBar` toggle ("P&L" | "In vs Out") switching the series — `SegTabBar` already exists and is used elsewhere. Removes one `card()` and its `set_series` block from `_AnalyticsOverview`; the paired-row layout that currently holds both becomes a single full-width card.

### Keep, but behind a flag / lower priority

- **Live bank sync via Basiq** (`bank_sync.py`). Real value, but heavyweight (API key, open-banking aggregator); CSV/OFX import (`importers.py`) already delivers reconciliation offline.
  - **How:** no removal — gate the Settings "Connect live" card behind a `settings["enable_bank_sync"]` flag (default off), so the always-on path is CSV import and sync is opt-in. Keep `bank_sync.py` as-is.

- **Cash-flow Sankey** (Analytics). Beautiful, low information-per-pixel for one person's monthly flow.
  - **How:** no code change needed now; mark it as the first card to drop if the page needs to shrink. If kept, leave it; if cut later, remove the `SankeyChart` card block from `_AnalyticsOverview` and the `cashflow_links` call — the widget/ backend can stay for reuse.

- **Renewal timeline + calendar heatmap** (Subscriptions) — two views of "when does it renew."
  - **How:** see §4 Subscriptions — merge into one (keep the timeline, drop the heatmap card, or overlay due-dots onto the timeline).

### Keep — genuinely core

Recurring ledger, budget-vs-actual, bank import + reconciliation, net worth, forecast, goals, subscription split math. These are the tracker.

---

## 4. Per-page efficiency — and how to build each

Theme: this app is **maintained**, not just viewed. Every recurring edit should be one inline gesture, not a dialog or page change.

### Top bar — turn the search into a filtered, keyword-aware search bar

Keep and upgrade the search (it is *not* fluff — for a dense tool it's the fastest way to jump to a buried item, note, or sub-item). Today `TopBar` has a magnifier that opens `SearchDialog` (`widgets.py:1932`) over `backend.search` (`backend.py:729`). The backend already recurses items → children (sub-items) and matches on `name + note + tags`, plus people/accounts/transactions — so the *substrate is already there*; what's missing is a real search **bar** (live, inline, filterable) on top of it and a few richer matches underneath.

The goal: type a keyword and immediately see every item, sub-item, subscription, person, account, or transaction whose **title, note, tag, or (for a sub-item) parent path** contains it — filterable by what kind of thing you're looking for.

**Backend — `backend.search` (`backend.py:729`):**
- **Widen the haystack.** Today `hay = name + note + tags`. Add the amount rendered as text (so `"2000"` finds Rent), the recurrence description (`repeat_label`), and the due date — all already on the node. One-line change to the `hay` join.
- **Carry parent path for sub-items.** The recursive `scan(children)` already finds sub-items but the result doesn't say it's a child or name its parent. Thread a `path` list down `scan` and return `parent` (and a full `path` string like `"Rent › Parking"`) on each hit, so a sub-item match is legible and navigable, not an orphan name.
- **Report the matched field.** Return `matched_field` ∈ {title, note, tag, amount, path} per result, so the UI can show *why* it matched (a note hit vs a title hit read very differently).
- **Add a `kinds` filter param.** `search(store, query, kinds=None)` — when a set is passed, skip scanning the entity types not requested. Cheap, and lets the filter chips (below) short-circuit instead of post-filtering. Keep the 60-cap but make it a `limit=` param.

**UI — inline bar + filter chips (`widgets.py` `TopBar` / `SearchDialog`):**
- **Replace the magnifier-opens-modal with an always-present inline `QLineEdit`** in the top bar (a small `SearchBar` widget), placeholder "Search items, notes, people…". `textChanged` → debounced (~150 ms) `backend.search` → a results popup anchored under the bar (a `QFrame` with `Qt.Popup`, or reuse the `SearchDialog` body rendered as a dropdown). Live, incremental — results narrow as you type, no Enter-to-search round-trip.
- **Filter chips row** at the top of the results popup: `All · Items · Sub-items · Subscriptions · People · Accounts · Transactions · Tags` as checkable chips (reuse `SegTabBar` or the same chip style as tags). Selecting one passes the matching `kinds` into `search` so the list re-filters instantly. "Tags" filters to matches whose `matched_field == "tag"`.
- **Each result row** shows: kind glyph, the name, the parent path when it's a sub-item (`under Rent`), and a dim right-aligned note of the matched field/snippet (`note: "cancel before renewal"`). Reuses the existing row styling in `SearchDialog`.
- **Keyboard-first.** `Ctrl+F` focuses the bar; `↑`/`↓` move the highlight through results; `Enter` navigates to the result's `target` page **and selects/scrolls to that item** (today it only switches page — extend the navigate handler to pass the item id so the destination page can highlight it); `Esc` closes the popup and clears focus.

**Where results go.** `search` already returns a `target` page key per hit; the only upgrade is carrying the item/sub-item id through so `MainWindow.go(target)` can scroll-to-and-flash the row rather than just landing on the page. For a person hit, land on the People tab with that card expanded; for a transaction, the Settings/import view filtered to it.

**Verification.** `pytest` for `backend.search`: keyword in a note returns the item with `matched_field="note"`; a query matching only a sub-item returns it with the correct `parent`/`path`; `kinds={"person"}` returns only people; an amount string (`"2000"`) matches by amount; empty query → `[]`; `limit` respected. Then a headless `MainWindow` screenshot of the inline bar with a query typed, the filter chips, and a sub-item result showing its parent path.

### Overview (the daily driver)
- **Inline amount/name edits are already present** (`LedgerCard._start`/`_commit`, `CategoryRow` inline commit) — good, keep. The remaining click-tax is the per-attribute popups (repeat/due/tag/note), which are multi-field and justified as popups; leave them.
- **Keyboard month nav.** *How:* add a `keyPressEvent` on `MainWindow` mapping `←`/`→` → `shift_period(∓1)`, `T` → `_goto_today` (both methods already exist and are wired to the top-bar arrows). ~10 lines.
- **"Mark paid" as a bigger target.** It's the highest-frequency action, currently a small hover control on the due column. *How:* make the whole due badge in `CategoryRow` a click target for the paid toggle, and add a single "mark all bills due this week paid" link in the expense card header that loops `store.edit_field(..., "paid", True)` over the week's due items.

### Analytics
- **Cross-filter is invisible.** Clicking a trend point or a month-table row filters the breakdown (`_on_trend_click`/`_on_month_click`) but nothing signals it. *How:* set `PointingHandCursor` on the clickable month rows (`Clickable` already supports a hover color; add the cursor) and add a one-line "click a month to filter ↓" caption under the table header.
- **Persist the selected sub-tab.** Overview/Income/Expenses resets to Overview every visit. *How:* store the last index on the `AnalyticsPage` instance (or in `settings`) and restore it in the tab-bar setup instead of hard-defaulting to 0.

### Goals
- **Fix the 578%-red ProgressBar first** (`widgets.py` `ProgressBar.paintEvent` overrun block — see the critique doc). A broken read beats any efficiency gain.
- **Inline "add to goal."** *How:* add a small `+$` control on each goal row in `GoalsPage._goal_row` that opens a one-field amount prompt and bumps `saved` on the goal record via the goals store, instead of routing contributions through linked-expense wiring.
- **Collapse projection charts by default.** Three stacked `LineChart`s for "am I on track" is heavy; the caption already answers it. *How:* wrap each goal's projection `LineChart` in a expandable row (a `Clickable` header that toggles the chart's visibility), collapsed by default.

### History
- **Bars have no stated scale.** *How:* either add a small right-aligned max-value label to the monthly-history bar card, or drop the bar and let the numbers (already shown) stand — the simpler fix.
- **Make months navigable.** *How:* the month rows are already `Clickable` in some views — wire each History month row's `clicked` to `goto_month(y, m)` (exists on `MainWindow`) so clicking jumps to that month's Overview instead of being a dead readout.

### Subscriptions
- **The people pipeline (§1) is the big win** — assigning members becomes the picker, not a text box.
- **Merge the two "when does it renew" visuals.** *How:* keep `SubscriptionTimeline`, remove the `CalendarHeatmap` card from `_build_subscriptions` (or overlay the due-dots onto the timeline). Frees a full card's height.
- **"Mark this cycle paid for everyone."** *How:* add a per-subscription action that loops `set_member_paid(sub_id, occ, person_id, True)` across the plan's members for the current occurrence — one click instead of N "Mark paid" buttons.

### Settings
- **Build the missing accounts UI** (`add_account`/`update_account`/`remove_account` exist in `datamanagement.py` but nothing calls them — net worth and forecasting depend on accounts a user can only add by editing JSON). *How:* a "Net worth accounts" card on `SettingsPage` next to the bank-connect card: list accounts, "+ Add account" opens an `AccountDialog` (same `PersonDialog` static-`.create()/.edit()` pattern), rows wired to `update_account`/`remove_account`. This is also the prerequisite for the stock feature in the other planning doc.
- **Mask the Basiq key field.** *How:* `key_field.setEchoMode(QLineEdit.EchoMode.Password)` on the API-key `QLineEdit` in `SettingsPage`.
- **Order by frequency of use.** *How:* reorder the `SettingsPage` cards so import/reconcile (monthly) sits above currency/week-style (set-once). Pure layout reorder.

### Cross-cutting
- **Keyboard-first navigation** (month arrows + tab switching) — the single biggest daily-speed win; the `keyPressEvent` above plus number-key page switching on the sidebar.
- **Remember view state** (selected sub-tab, month lens) between visits — persist to `settings`, restore on load.
- **Every one-field dialog is a click tax** — the recurring theme; prefer inline commit wherever the edit is a single value.
