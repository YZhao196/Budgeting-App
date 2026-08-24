# Budgeting Tool — full app reference

A complete catalogue of what the app does and exactly how it's built, as of the
current codebase. This supersedes `DESIGN.md` in accuracy — that file still
describes the pre-Notion-overhaul flat/0px-radius aesthetic ("no rounded
corners… anywhere"), which the app no longer follows. `PRODUCT.md` remains
accurate at the strategic level; this document is the exhaustive one.

---

## 1. What it is

A single-user personal finance desktop app (PyQt6, Windows) built on one idea:
**the plan and the bank statement are held to the same standard, in the same
place.** Most budgeting tools pick one — a forecast you trust but never check,
or a reconciled report with no sense of what was supposed to happen. This app
keeps a recurring-item ledger (what *should* happen) and bank-imported,
reconciled transactions (what *did* happen) live at once, at equal visual
weight.

**Audience:** one person, at a desk, checking in regularly — not a product for
distribution. Precise and information-dense rather than simplified.

**Stack:** PyQt6. Every chart is hand-painted with `QPainter` — no charting
library. Business logic (`backend.py`) is pure Python with no Qt dependency,
independently unit-tested. Data persists to a flat JSON store (`data/`,
gitignored) via `ItemStore` (`datamanagement.py`).

---

## 2. Pages

The sidebar has six destinations. Two (`Overview`, `Settings`) are always
visible; the rest can be hidden per-user in Settings.

### 2.1 Overview
The home page — "am I on track?" answered in one glance.

- **Incoming / Outgoing ledger cards**, side by side. Each row: name
  (click-to-edit), recurrence glyph, amount (click-to-edit, sign-coloured),
  due date, paid toggle, priority dot, tag chips, and a hover-revealed action
  column (recurrence / tag / note / delete).
- **Custom / By Due / By Added** sort tabs per ledger.
- **Weekly P&L breakdown** for the current period.
- **Hero P&L number** — the single largest, brightest figure on the page
  (`GREEN_BRIGHT`), with a count-up animation on month change.
- **Monthly / Yearly / YTD** toggle on the summary card.
- **5-month P&L sparkline trend.**
- **Predicted income — next month**, from recurring sources.
- **Savings-goal progress bars** across the bottom.
- A fixed ~356px right rail hosts the summary stack; the two ledger columns
  fill the remaining width dynamically.

### 2.2 Analytics
A dense, three-tab dashboard. Unlike every other page, it's **not** bounded to
the 1100px reading column — it fills the full window width and reflows live on
resize, because it's a data-dashboard surface, not a prose-shaped one.

**Overview tab:**
- Avg income/expenses/P&L/savings tile row, each with a sparkline.
- Best month / worst month / months-positive / income-growth tile row
  (colour-by-sign, not by rank — see §6).
- **Month-by-month table**, paired side-by-side with **spending composition**
  (a stacked bar chart) — complementary views of the same history, sharing one
  row instead of each wasting width alone.
- **Budget vs actual** — a grouped/bullet bar chart, full width (bars need the
  room); collapses to an empty state when no budgets are set.
- **Liquid-balance forecast** — a 6-month projection band, full width.
- **P&L trend paired with the category-breakdown donut** — the trend says
  "click a point to filter breakdown," so the donut it drives sits right next
  to it.
- **Predicted income** (tall: chart + recurring-sources list) paired with a
  stacked right column of **Budget vs actual** + **Plan vs actual**, height-
  balanced against it.

**Income / Expenses tabs:** per-kind breakdown donut + trend, then the full
ledger for that kind (`LedgerDetailPage`). Also unbounded/full-width.

### 2.3 Subscriptions
Three sub-tabs:
- **Subscriptions** — total count, monthly cost, amount owed to you; a
  **spending & due-dates calendar** (borderless — see §6); a **renewal
  timeline** (next 60 days, dot-plot); a list of subscriptions with cost
  splits, "waiting on" indicators for unpaid shares, and mark-paid actions.
- **People** — everyone you split subscriptions/consumables with, what they
  owe, settle-up actions.
- **Consumables** — one-off or recurring shared purchases tracked the same
  way as subscriptions.

Detects untracked recurring bank charges (a bill that shows up repeatedly in
imports but isn't in the ledger).

### 2.4 Goals
- Actual P&L / Target P&L / Savings-rate tiles.
- **Progress to target** bar — clamps visually at 100% and switches to
  "met · $X over" past it rather than reporting a nonsensical percentage like
  578%.
- **Savings goals** — target amount, linked expenses, projected completion
  date ("if all savings went here, by <month>"), expandable projection chart.
- **Edit monthly targets** — Target P&L and Weekly budget, laid out as
  Notion-style property rows (fixed label column, value immediately beside
  it) rather than a label-then-1400px-later-field.

### 2.5 History
- Total saved / avg-per-month / best-month / months-tracked tiles.
- **Cumulative savings** area chart.
- **Monthly history** — one row per month, fixed-column layout (month name |
  progress bar | in | out | P&L), so a row's five facts cluster instead of
  spanning the full window width.

### 2.6 Settings
Sectioned, in "getting data in" order:
- Currency symbol, week-view style (ISO Mon–Sun vs. month-aligned).
- Sidebar tab visibility toggles.
- **Connect bank accounts** (ANZ/ANZ Plus) — CSV/OFX import, review-
  transactions dialog, clear-imported (confirmed — destructive).
- **Live bank sync (Basiq)** — API key + user ID fields, Connect/Sync now
  buttons; explicitly labelled a scaffold ("untested until you add a key").
- **Categorisation rules** — substring-match rules mapping transaction text to
  a category, with an autocomplete of existing expense names.
- **Net-worth accounts** — manual account balances feeding the net-worth
  calculation (the *graph* of this was removed from Analytics per a later
  request; the accounts feature itself remains).
- **Export data (CSV)**, **Modules** (user plugin discovery from
  `data/modules/*.py`), **Danger zone** (reset).

---

## 3. Cross-cutting features

- **Recurring items** — weekly, monthly, custom intervals, specific days of
  month, with an anchor-relative recurrence engine (`occurrence_dates`).
- **Shared plans / people** — split subscriptions and consumables with named
  people; per-person owed/paid tracking; settle-up.
- **Bank import & reconciliation** — CSV/OFX importers, auto-categorisation,
  plan-vs-actual budget reports.
- **Command palette (`Ctrl+K`)** — 29 actions, subsequence-fuzzy matched
  ("jul" finds "Jump to Jul 2026"): page navigation, month jumps to any month
  with data, add income/expense, import, review transactions.
- **Global search (`Ctrl+F`)** — across items, subscriptions, people,
  accounts, transactions.
- **Keyboard layer** — `Ctrl+1`–`5` pages, `Ctrl+,` Settings, `Ctrl+←/→` month
  stepping, `Ctrl+T` today, `Ctrl+\` sidebar collapse.
- **Fluid UI scale** — fonts and text-sized controls scale ~0.92×–1.16× with
  window width (1280→2400px band), debounced on resize. The default 1680px
  window sits at ~1.0×.
- **User module system** — drop a `.py` file in `data/modules/` implementing
  a small API (`add_page`, helpers) to add a custom sidebar page.

---

## 4. Design system

### 4.1 Aesthetic lineage — two eras
The app went through a deliberate pivot mid-project: it started as a
zero-radius "trading terminal" (flat, sharp, explicitly anti-Mint/YNAB/Monarch
— documented in the now-stale `DESIGN.md`), then was rebuilt on **Notion's
structural model** (bounded reading column, borderless blocks, whitespace-led
grouping, text sidebar) while **keeping the dark palette** — Notion-structure
in Notion-dark, not a light-mode clone. A later pass then **rounded** the
theme further (radius 0→3→5→9) because sharp corners read as "clinical," not
"user-friendly."

### 4.2 Colour

| Token | Hex | Use |
|---|---|---|
| `BG_APP` | `#111111` | window base |
| `BG_SIDEBAR`/`BG_HEADER` | `#181818` | nav rail, top bar |
| `BG_CARD` | `#1e1e1e` | the standard surface (blocks are otherwise transparent) |
| `BG_CARD_SOFT` | `#242424` | nested tiles |
| `BG_TAG` | `#242424` | neutral tag-chip fill |
| `BG_INPUT` | `#1e1e1e` | field fill — *lighter* than the page, Notion-style |
| `TEXT` / `TEXT_MUTED` / `TEXT_DIM` | `#d4d4d4` / `#9a9a9a` / `#909090` | primary/secondary/tertiary |
| `GREEN` / `GREEN_BRIGHT` | `#5da876` / `#74c490` | income, on-track / the one hero figure |
| `RED` / `RED_BRIGHT` | `#cc7676` / `#e08c8c` | expense, negative |
| `AMBER` | `#c8944a` | due-soon, budget-pace warning |
| `FOCUS` | `#2f8ae5` | keyboard focus ring — its own hue, shared with nothing |
| `SERIES` (8 steps) | slate, steel-blue, mauve, gold, purple, teal, copper, yellow-green | categorical breakdowns only, never functional |

**Rules, still enforced:**
- **Colour is a mark, not a surface.** Stat boxes lost their tinted fill —
  the coloured *number* is the signal, not a green rectangle behind it.
- **Colour by sign, never by rank.** "Worst month" is red only if the value
  is actually negative — a positive "worst" month renders in green, because
  colour answers "is this bad," not "is this the smallest."
- **The pie/donut breakdowns use a sign-based green/red ramp**
  (`sign_ramp()`), not the categorical `SERIES` palette — an expense
  breakdown is a family of reds, an income breakdown a family of greens,
  ordered light→dark by share size. The stacked "spending composition" bar
  still uses `SERIES` (many categories, no single sign to key off).
- **Focus has its own hue.** It used to share a hex with `GREEN_BRIGHT` (the
  hero number) — fixed so a focus ring and "the most important figure on the
  page" can't be confused.

### 4.3 Typography
**Arial Nova** (regular) for all UI text; **Arial Nova Light** for large
display numbers (≥18px) — one family, two weights, not a pairing. Five-step
scale: `FS_MICRO 11 / FS_BODY 14 / FS_HEAD 16 / FS_METRIC 20 / FS_HERO 30`,
each a genuinely visible jump (the old seven-step 9–15px scale sat below the
just-noticeable-difference threshold). All of it additionally scales with the
fluid UI-scale factor (§3).

### 4.4 Spacing & radius
Soft 8pt grid: `SPACE = [4, 8, 12, 16, 24, 32, 48]`. `BLOCK_GAP=40` between
blocks, `GAP_SECTION=48` between topic clusters — deliberately larger than
`BLOCK_GAP` so a topic shift still reads as a bigger break. `RADIUS=9` on
panels/inputs/buttons/menus/dialogs; `RADIUS_SM=6` on chips/bars/calendar
cells/focus rings; `RADIUS_PILL` fully-rounded ends on progress bars and
segmented pills.

### 4.5 Layout
- **Content column** capped at `CONTENT_MAX_W=1100` and centred, on every
  page *except* Analytics (which is a dashboard, not prose, and fills the
  window). The header rides the same column as the body so the title aligns
  with content, not the window edge.
- **Sidebar**: 240px, full text labels (was a 72px icon-only rail whose 9px
  captions truncated — "Quick start" → "Quick sta…"), collapsible to 48px via
  `Ctrl+\`.
- **Scroll gutter**: 16px reserved between scrollable content and the
  scrollbar, so text never runs flush against the 10px bar.
- **Property rows / fixed-column rows** replace the old "label — stretch —
  value" pattern wherever a label and its value used to end up 1000px+ apart
  on a wide window (Goals' target editor, History's monthly rows).

### 4.6 Components
- **Blocks, not cards.** No resting border or fill on page-level surfaces —
  grouping comes from whitespace (`BLOCK_GAP`), not a box. The one exception:
  the Incoming/Outgoing ledger cards keep a 2px green/red top rule, because
  there the colour is functional (which ledger this is), not decorative.
- **Inputs**: fill only at rest, no border; a faint border on hover; `FOCUS`
  border only on real focus — so focus is a real state-change on a calm
  default, not a colour-swap on an already-loud box.
- **The Subscriptions calendar is borderless** — the old version stroked all
  42 day cells; now only cells that carry data (spend, hover, today) draw
  any ink, with faint week-row hairlines for structure.
- **Tag chips**: quiet neutral pill (`BG_TAG`, no border), not
  accent-coloured — a tag is metadata, not a state, so it doesn't borrow
  green's "on-track" meaning.
- **Charts**: gridlines route through a single `GRID` token, deliberately
  fainter than dividers, so the data line/bars are always the loudest ink on
  the chart.
- **Buttons**: a shared filled/outline vocabulary (`_button`/`_btn`) with a
  disabled state (greyed) and a consistent focus ring across both factories.
- **Row action glyphs** (recurrence / tag / note / delete): custom vector
  icons (`icons.py`, unit-circle line-drawn style — same convention as the
  nav icons), consolidated into one right-aligned column, hidden until row
  hover *except* when "lit" — a recurring item or one with a note keeps that
  glyph visibly on as a status marker, not just an affordance.
- **Click-to-edit affordance**: editable name/amount fields show a dotted
  underline on hover/focus, so an editable value is discoverable within one
  hover rather than looking like plain text.

### 4.7 Motion
Short and functional, never decorative: 130ms page-crossfade, 180ms row
fade-in on insert, 280ms hero-number count-up, 340→200ms chart reveal. All
gated behind an `ANIMATE` flag that's off during headless screenshot capture,
so `--shot` output is always deterministic.

### 4.8 Accessibility
- Every text/background pairing in the shipped palette clears WCAG AA
  (4.5:1) — `RED` was lifted from `#b86060` (3.87:1, failing) to `#cc7676`
  (5.10:1) specifically because it's used on 13px-bold expense amounts,
  which don't qualify as WCAG "large text."
- Sign is carried by colour **and** a `+`/`−` prefix, never colour alone.
- Custom-painted widgets draw their own rounded focus ring
  (`draw_focus_ring`); standard Qt controls get the same `FOCUS` colour via
  global QSS, so keyboard focus is visible everywhere, not just on native
  widgets.

---

## 5. Design principles (the "why")

Distilled from `PRODUCT.md` plus decisions made through the Notion-critique
and subtractive-pass work:

1. **Numbers lead; chrome doesn't compete.** Every screen's first job is a
   number or a trend.
2. **Plan and reality are peers.** The recurring ledger and the bank-
   reconciled view get equal visual weight — neither is the "advanced mode"
   of the other.
3. **Dense inside a block, calm between blocks.** The resolution to density-
   vs-Notion-calm: a ledger or a month-table may be dense; the page around it
   must breathe. Whitespace is spent between blocks, not inside the data.
4. **Functional colour only, and colour is a mark, not a surface.** Green/
   red/amber always encode a real state, always paired with a label,
   position, or sign — never decorative, never a passive fill behind
   content.
5. **Calm under bad news.** Deficits and overruns are reported in the same
   flat visual language as good news — no alarm chrome.
6. **Borders exist only where they carry information** — a focus ring, a
   row-divider, a functional top-rule. Not around every panel, cell, or
   chip by default.
7. **Every clickable/editable thing should look it within one hover** —
   discoverability without prior knowledge, balanced against keeping the
   resting surface quiet.
