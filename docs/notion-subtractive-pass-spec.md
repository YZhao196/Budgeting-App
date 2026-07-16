# Implementation spec — the Notion "subtractive" pass

Turns the critique in [ux-critique-borders-decoration-notion.md](ux-critique-borders-decoration-notion.md)
into an executable plan: remove the borders, fills, and redundant colour that
still make the app feel like a bordered dashboard, and spend the whitespace
Notion's calm is made of. Every item lists the exact location, the current code,
the change, the before/after, how to verify, and the risk.

**Principle throughout:** *replace chrome with space or fill, never add chrome.*
Every change is subtractive or a like-for-like swap — nothing new is drawn.

**Grounding:** Filipiuk = *UI Design Principles*; Henderson = *UI/UX Design Guide*.
Cited by page. Code line numbers are as of this writing — re-grep before editing.

---

## 0. Token changes (do first — everything below leans on these)

`theme.py`. These are the shared levers; changing them alone does ~30% of the work.

| Token | Now | New | Why |
|---|---|---|---|
| `RADIUS` | `3` | `5` | Filipiuk p132: rounder = *more user-friendly*. 5px is Notion's register — humane, not bubbly. |
| `RADIUS_SM` | `3` | `4` | Chips/small controls, one step tighter than panels. |
| `BORDER_SOFT` | `#202020` | `#1c1c1c` | Used for gridlines/dividers; drop it nearer the background so a hairline whispers instead of speaks. |
| `GRID` *(new)* | — | `#181818` | A dedicated, fainter-than-BORDER_SOFT pen purely for chart gridlines (§4). Keeps dividers and gridlines independently tunable. |
| `BG_TAG` *(new)* | — | `#242424` | Muted neutral tag fill (§3). Not a functional colour. |
| `SP_ROW` *(new)* | — | derive from `ROW_H` | See §5; lets the whitespace pass move one number. |

**Verify:** `python main.py --shot` every page; confirm nothing regressed and the
corners read slightly softer. `python -m pytest -q` (118 should stay green — these
are cosmetic).

---

## 1. Subscriptions calendar → borderless month  *(highest impact)*

**Why.** The single busiest, noisiest surface in the app. `CalendarHeatmap`
(`widgets.py:4394`) strokes **42 day-cell rectangles**, most empty. Filipiuk p34:
when every region is closed, closure carries no information; Henderson p76: that's
pure extraneous cognitive load. A month grid needs structure, not 42 outlines.

**Location.** `widgets.py` `CalendarHeatmap.paintEvent`, the cell loop (~`4478`):
```python
p.drawRect(rect)                     # ← the outline on every cell
...
if amt > 0:
    fill = QColor(T.RED); fill.setAlpha(...)
    p.setBrush(fill); p.drawRect(rect)
if day == self._hover:
    hl = QColor(T.BG_HOVER); hl.setAlpha(120)
    p.setBrush(hl); p.drawRect(rect)
```

**Change.**
1. **Delete the resting `p.drawRect(rect)` outline.** Cells get no border.
2. Keep the *spend fill* (`amt>0`) and the *hover fill* — those carry data, so
   draw them as **filled, no-stroke, rounded** rects (`drawRoundedRect(rect,
   RADIUS_SM, RADIUS_SM)`, `setPen(NoPen)`).
3. Separate weeks with **one hairline per row** in `GRID` (six thin horizontal
   lines) — or nothing; try both. That is the only border the grid keeps
   (Notion table style, critique §6.6).
4. Keep the day-number (top-left, `TEXT_DIM`) and the today-outline (the one cell
   that *should* stand out now genuinely does, since it's the only stroked thing).

**Before/after.** 42 outlined boxes → a clean field where only *today*, *days with
spend* (shaded), and *event dots* carry ink. The 3 meaningful cells stop hiding in
a lattice of 39 empty ones.

**Verify.** `--shot --page subscriptions`; the calendar should read as a calm grid,
today clearly the only outlined cell, spend-days shaded, dots visible.

**Risk.** Low. Pure paint change, no layout/data touch. Watch that week-rows stay
legibly separated without the cell borders — add the hairline if they blur.

---

## 2. Inputs → fill, not box

**Why.** Every field carries a resting `1px` border *and* a focus border, so focus
is a weak colour-swap on an already-loud box (Filipiuk p133: a state should be a
clear change from a *calm* default). Notion: a field is a slightly-different fill,
border only on focus.

**Location.** `theme.py` `global_qss()`:
```python
QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox {{
    background: {BG_INPUT};
    border: 1px solid {BORDER_LIGHT};      # ← resting border
    border-radius: {RADIUS}px; padding: 6px 9px; ...
}}
QLineEdit:focus, ... {{ border: 1px solid {FOCUS}; }}
```

**Change.**
```python
QLineEdit, QComboBox, ... {{
    background: {BG_INPUT};
    border: 1px solid transparent;         # reserve the space, show nothing
    border-radius: {RADIUS}px; padding: 6px 9px; ...
}}
QLineEdit:hover, ... {{ border: 1px solid {BORDER}; }}   # faint on hover
QLineEdit:focus, ... {{ border: 1px solid {FOCUS}; }}    # real state on focus
```
The `transparent` resting border keeps the box model identical (no layout shift
when the border appears), so the field reads as editable **by being a lighter
fill than the now-transparent block** — exactly Notion's mechanism.

**Caveat — the inline overrides.** Several fields set their own stylesheet inline
(e.g. `SettingsPage` rule/basiq fields at `main.py:~1487`, `SearchDialog`,
`CommandPalette`) with `border:1px solid BORDER_LIGHT`. Grep
`border:1px solid {T.BORDER` and give each the same resting-transparent treatment,
or they'll stay boxed while the global ones go quiet (Henderson p80 #4 —
consistency).

**Verify.** Tab through Settings and a dialog: at rest fields are quiet fills; on
focus a clear `FOCUS` ring appears. No 1px jump when focus lands (that's the
`transparent` reservation working).

**Risk.** Medium — the inline-override sweep is the fiddly part; miss one and it's
visibly inconsistent. Do the grep, don't eyeball it.

---

## 3. Kill decorative colour fills → colour marks, not colour surfaces

**Why.** Green/red have drifted from *marks* to *surfaces* (critique §3.1). When a
green number sits on a green fill inside a green-bordered box, three greens say one
thing, and when most of a page is green, green stops meaning "good" (Henderson
p118). Notion keeps surfaces monochrome and lets one coloured *word* carry meaning.

### 3a. StatBox (Incoming / Outgoing on Overview)
**Location.** `widgets.py:3388` `StatBox`, and its uses `widgets.py:3458`:
```python
self.setStyleSheet(f"QFrame{{background:{bg}; border:none;}}")   # bg = GREEN_BG / RED_BG
```
**Change.** `background: transparent`. Keep the coloured **number** and label
(they're the mark); drop the tinted rectangle. Separate the two boxes with space,
not fills. The `bg` param becomes unused — delete it from the signature and the two
call sites (`StatBox("Incoming", "", T.GREEN)`), don't leave dead args.

### 3b. Tag chips
**Location.** `widgets.py` `_TagChip`:
```python
f"color:{T.ACCENT}; background:{T.BG_INPUT};"
f"border:1px solid {T.BORDER}; border-radius:7px; padding:1px 6px;"
```
**Change.**
```python
f"color:{T.TEXT_MUTED}; background:{T.BG_TAG};"          # muted, neutral
f"border:none; border-radius:{T.RADIUS_SM}px; padding:1px 7px;"
```
A tag is *metadata*, not a state — so it should be a **quiet neutral pill**, not an
accent-coloured bordered one (Notion tags are low-saturation tints). This also
frees green/accent to mean "income/on-track" again. (If you want per-tag colour
later, use `T.category_color(text)` as low-alpha text — but neutral-first.)

### 3c. Deficit banner / other `*_BG` fills
Grep `T.GREEN_BG`, `T.RED_BG`. The **deficit banner** (`widgets.py:3487`) is a
legitimate keep — a red wash on genuinely bad news is a real state, and the brand
explicitly allows it. The *button* fills (`GREEN_BG` on Save buttons) are the
primary-CTA style and stay (Filipiuk p131: the important button *should* stand
out). Only the **passive stat surfaces** (§3a) lose their fill. Be surgical — this
is "remove decorative fill", not "remove all colour".

**Verify.** Overview: Incoming/Outgoing are coloured numbers on the plain block,
no tinted boxes. Ledger tags are quiet grey pills. Save buttons still filled green.
Deficit banner still red.

**Risk.** Low, but requires judgement per `*_BG` site (keep CTA + banner, drop
passive). Don't blanket-replace.

---

## 4. Chart de-ornament

**Why.** Gridlines currently draw in `BORDER_SOFT` at full 1px — solid hairlines
that compete with the data line (critique §3.2). On a 8–10 chart dashboard that's a
lot of secondary ink. The gridline should be the *faintest* thing on the chart.

**Location — single point.** `widgets.py:4007` `draw_axis()`:
```python
grid_pen = QPen(QColor(T.BORDER_SOFT), 1)
```
**Change.** `grid_pen = QPen(QColor(T.GRID), 1)` (the new fainter token, §0). One
line changes every chart that uses the shared helper. Optionally reduce the number
of gridlines (draw every other `step`) so there are 2–3, not 4–5.

**Also.** Axis ticks (`widgets.py:4857`, `drawLine(..., axis_y-3, ..., axis_y+3)`)
— shorten to 2px or drop; the label alone locates the axis. The flat-line demo
case is the tell: a P&L trend that's a straight line shouldn't ship a 5-line
lattice around it.

**Verify.** `--shot --page analytics`; the data lines/bars are clearly the loudest
ink; gridlines are a whisper you notice only when you look for them.

**Risk.** Low. If `GRID` is *too* faint on some backgrounds, it's a one-token nudge.

---

## 5. The whitespace pass  *(the one that most "feels like Notion")*

**Why.** Filipiuk p223–233: whitespace is the structuring mechanism, not the
leftover; p227 *"fewer elements → more focus on the ones there"*; p229 *"don't
fill it without a good reason."* The app rations space (32px rows, tight
line-height, 24px sections). Notion spends it. This change alters almost nothing on
screen except the *air*, which is the point.

**Changes (all in `theme.py` / a few call sites):**
1. **Row height** `ROW_H 32 → 34` (`widgets.py`). A hair more room per ledger row;
   with the fluid font scale this keeps text off the row edges.
2. **Block spacing** `BLOCK_GAP` (= `SP_2XL` = 32) → `40`. More air *between*
   blocks — the Notion between-block calm.
3. **Line-height on wrapped body copy.** Empty-state and description labels
   (`setWordWrap(True)` sites) get `line-height` via a stylesheet or a small
   `QLabel` margin; target ~1.4–1.5 (Notion runs ~1.5). Filipiuk p53 (baseline).
4. **Section rhythm.** Leave `GAP_SECTION` as the larger "paragraph break"; the
   contrast between `BLOCK_GAP` and `GAP_SECTION` is what signals topic shifts.

**Critical rule (Filipiuk p229):** *do not refill the space you free.* The whole
value is the emptiness. Resist the reflex to add a chart to the gap.

**Verify.** Side-by-side `--shot` before/after: same content, more air, calmer. If
it now scrolls one screen more, that's acceptable — calm > density on a tool you
sit with (this is the §8 tension, resolved toward calm *between* blocks).

**Risk.** Low mechanically; the risk is *taste* — too much air on a dense page
feels empty. Tune `BLOCK_GAP` by eye at 36/40/44.

---

## 6. Standardise buttons to a 3-tier system

**Why.** Three helpers (`_button`, `_btn`, `Clickable`-as-button) produce filled /
line / text-link styles (Filipiuk p130) that aren't *mapped to importance*
(p131: "the more important the button, the more it stands out"). Same action can
look different in two places (Henderson p80 #4).

**Change.** One helper, three explicit tiers:
```python
def button(text, tier="secondary", on_click=None):
    # primary   : filled ACCENT, ON_ACCENT text        (Save, Add, primary CTA)
    # secondary : transparent + 1px BORDER, TEXT        (Cancel, Close, neutral)
    # tertiary  : text-link, ACCENT on hover, no box    (+ Add item, Set budgets…)
```
Migrate `_button`/`_btn` call sites to `button(..., tier=...)`. `Clickable` stays
as the tertiary/text-link primitive. All three get the p133 states: default /
hover / **disabled** (grey, `setEnabled(False)` actually reflected visually).

**Verify.** Every dialog and page: primary action is the one filled thing; cancels
are outlined; inline adds are text-links. No two "Save"s look different.

**Risk.** Medium — many call sites. Do it mechanically, one dialog at a time, shot
each.

---

## 7. Make click-to-edit discoverable

**Why.** Ledger names/amounts are click-to-edit but look like plain text at rest
(Filipiuk p281: clickable must *look* clickable; Henderson p80 #6 recognition).
Combined with hover-only action glyphs, much of the UI is invisible until you
already know it's there — fine for the author today, a wall for the author in six
months.

**Change (subtle, not chrome).** On the editable `Clickable` name/amount, add a
**resting affordance**: a 1px dotted underline in `TEXT_DIM` that brightens to a
solid `FOCUS` underline on hover — or a faint `BG_HOVER` fill on the cell on row
hover with a text-cursor. Keep it *quiet* (this is calm-surface territory) but
*present*. Pair with the existing `Ctrl+K` palette as the discoverable escape
hatch (critique §8).

**Verify.** A cold user can tell the numbers are editable within a hover, without a
tooltip.

**Risk.** Medium taste risk — too strong an affordance re-clutters the row. Dotted-
underline-on-hover-only is the minimal version; start there.

---

## 8. Language pass (cheap, high-clarity)

**Why.** Filipiuk p253 "sound as human as possible"; Henderson p122 microcopy.
Jargon leaks: `P&L`, `Pr`, `ISO weeks (Mon–Sun, cross-month)`.

**Changes.** `P&L` → `Net` (or `Profit`) app-wide; `Pr` column → a priority icon
with a tooltip, or the word; rewrite the week-style option in plain terms
("Weeks that cross month boundaries" vs "Weeks reset on the 1st"). Grep each
literal; they're display strings, low-risk.

**Verify.** No un-glossed accounting/dev abbreviation on any default screen.

**Risk.** Low.

---

## Sequencing & effort

| # | Item | Effort | Impact | Risk | Order |
|---|------|:--:|:--:|:--:|:--:|
| 0 | Tokens (radius, GRID, BG_TAG) | XS | Med | Low | 1st |
| 1 | Borderless calendar | S | **High** | Low | 2nd |
| 3 | Kill decorative fills | S | **High** | Low | 3rd |
| 2 | Inputs fill-not-box | M | Med | Med | 4th |
| 4 | Chart de-ornament | XS | Med | Low | 5th |
| 5 | Whitespace pass | S | **High** (feel) | Low | 6th |
| 8 | Language pass | S | Med | Low | 7th |
| 6 | Button 3-tier | M | Med | Med | 8th |
| 7 | Click-to-edit affordance | M | Med | Med | 9th |

**Items 0–5 are ~a day and deliver most of the perceived change** — they're the
subtractive core. 6–7 are the consistency/discoverability follow-up. Do 0 first
(everything leans on it); do 1 and 3 next (highest noise removed per line changed);
save 6–7 for when the surface is already calm.

## Acceptance criteria (how you know it's "Notion enough")

- No panel, cell, tile, chip, or input carries a **resting** border. Borders exist
  only as: focus rings, single row-dividers, and the ledger's functional top-rule.
- Colour appears only as **marks** (a number, a word, a dot, a bar) — never as a
  passive **surface** behind primary content. Green means income/on-track and
  nothing else the eye can confuse it with.
- Gridlines are the faintest ink on every chart.
- Every editable thing looks editable within one hover.
- The page breathes: more air between blocks than inside them.
- 118 tests still green (all of the above is cosmetic/paint — none touches logic).

## The tension, restated (from critique §8)

Density and Notion-calm fight. Resolve them the way Notion does: **dense inside a
block, calm between blocks.** A ledger or a month-table may be dense; the *page*
around it must breathe. Every item above pushes noise out of the between-block
space and leaves the genuine data density alone. That's the line to hold — don't
"simplify" the data (that's the app's earned complexity), *subtract the chrome
around it*.
