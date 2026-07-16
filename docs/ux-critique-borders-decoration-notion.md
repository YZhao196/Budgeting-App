# Heavy critique: layout, borders, decoration — and what Notion does right

**Scope.** A hard look at why the app, *as it stands now* (after the block/glyph/
scale work already landed), still fights its user — narrowed to the four things
asked for: **layout, design choices, borders, decoration.** Then a deep read of
Notion's design language and how to bring it here.

**Grounding.** Every claim ties to what's on screen in the current build (fresh
`--shot` of all six pages) and to the two references: *UI Design Principles*
(Filipiuk) and *UI/UX Design Guide* (Henderson), cited by page. No claim from
memory.

**Honest disclaimer.** A lot of the earlier damage is already undone — cards are
de-bordered blocks, the sidebar is text, the action glyphs are consolidated. So
this isn't "it's all broken." It's the *next* layer: the borders and decoration
that survived, and the layout habits that a block system alone doesn't fix.

---

## 1. The one-sentence thesis

**The app still uses lines and colour to do jobs that space and hierarchy should
do — so the eye is constantly told "these things are separate / this is
important" by chrome, when it could be told the same thing, more calmly, by
emptiness.** That is the exact failure Filipiuk p35 (figure-ground) and Henderson
p80 #8 (aesthetic-and-minimalist: *"every extra unit of information competes with
the relevant units"*) both name, and it's the single axis on which Notion most
outclasses this UI.

---

## 2. Borders — still the biggest offender

De-bordering `card()` fixed the page-level panels. But borders retreated into the
components, where they're now doing the most damage because they're densest.

### 2.1 The Subscriptions calendar is a wall of boxes
`CalendarHeatmap` (`widgets.py:4394`) draws a 7×6 grid where **every day is a
bordered cell** — 42 rectangles, each outlined, most empty. This is Filipiuk p34
(common region) turned against itself: *"elements within a closed region are
perceived as a group"* — but when all 42 regions are closed, closure means
nothing, and the eye has to scan a grid of identical frames to find the 3 cells
that actually carry a dot. Henderson p76 calls the cost by name: **extraneous
cognitive load** — effort created purely by presentation, contributing nothing to
the task. A real calendar month has structure without 42 outlines: hairline
row-separators (or none), the day-number in the corner, and colour only where
something is due. The borders are 95% noise.

### 2.2 Inputs are darker-and-boxed instead of lighter-and-quiet
Every `QLineEdit`/`QComboBox`/spin-box carries a full `1px BORDER_LIGHT` frame
(`theme.py` global QSS). On the now-transparent blocks that reads as a hard
rectangle floating on the page. It's *necessary* that a field look editable — but
a full box is the heavy way to say it. Notion says it with a **fill alone** (a
field is a slightly lighter rectangle, no border) and a border only on focus.
Here the field is bordered at rest *and* on focus, so focus is a colour-swap on an
already-loud element — weak feedback on a noisy base (Filipiuk p133: states
should be a clear change from a calm default).

### 2.3 The month pill, the segmented tabs, the tag chips
Three more bordered survivors, each small, together constant:
- **`JULY 2026`** sits in a bordered pill (`MonthNav._style_lbl`) — a box around a
  label that's already obviously the title of the view.
- **`Fixed` / `Home` tag chips** on ledger rows (`_TagChip`) are bordered, filled
  pills — decoration on a data row that already has six columns competing for the
  eye.
- The **`Month | Week`** and **`Custom | By Due | By Added`** segmented controls
  are bordered pill-groups.

None is fatal alone. The point is *accumulation* — Henderson p110's "papercut
bug": no single border is wrong, but the interface is death-by-a-thousand-frames,
and the reader feels it as "busy" without being able to name why.

### 2.4 The ledger's green/red top-rule
`LedgerCard` keeps a `2px` green (income) / red (expense) rule across the top of
each card. I defended this earlier as *functional* colour — and it is — but it's
worth challenging: the card already says "Incoming ▲" / "Outgoing ▼" in words and
a glyph, and every amount below carries a sign and colour. The top-rule is a
*fourth* redundant encoding of the same fact. Filipiuk p35: it's foreground chrome
that isn't earning its contrast.

**The through-line:** borders here are almost never load-bearing. Nearly every one
could be replaced by whitespace, a fill, or nothing, and the screen would lose
noise without losing a single piece of information.

---

## 3. Decoration — colour and ornament doing too much

### 3.1 Functional colour has become ambient colour
The brand rule is "green=income, red=expense, amber=warning, never decorative."
The rule is good; the *application* has drifted into decoration:
- The **Incoming / Outgoing** stat boxes (`StatBox`, `widgets.py:3388`) are filled
  green-tint / red-tint **rectangles**. That's colour as a *surface*, not as a
  data mark — a green field behind a green number behind a "+". Three greens
  stacked to say one thing.
- On Analytics, the tile row shows **six green values in a column** (avg income,
  avg P&L, best month, savings, months-positive, growth). When most of the page
  is green, green stops meaning "good" and starts meaning "text." Henderson p118:
  if colour is going to carry meaning, it can't be everywhere, or it carries none.
- The **priority squares** (`PriorityCell`) are a third colour system (red/amber/
  green dots) layered onto rows that *also* use red/green for money and amber for
  due-soon. Same three hues, third meaning. The user now has to know *which* red
  they're looking at.

Filipiuk's colour chapter (p89–95) is blunt: each colour should evoke *one* thing.
This app has green meaning income, positive-P&L, on-track, low-priority, and
"reached" — five jobs for one hue. That's not functional colour; it's a colour
that's been asked to mean whatever is nearby.

### 3.2 Chart ornament
The charts carry full horizontal gridlines, axis ticks, and axis labels on every
panel. On a dashboard of 8–10 charts that's a lot of secondary ink. Tufte's
data-ink principle (the spirit of Henderson p80 #8) says the gridlines should be
the faintest thing on the chart or absent; here they're solid hairlines competing
with the data line. The P&L trend that's a *flat line* (demo data) still ships a
full 4-gridline lattice around it.

### 3.3 The `$` logo
A bold green `$` in the sidebar header. It's fine, but it's the one purely
decorative mark in a tool that otherwise earns every pixel — worth noting only
because Filipiuk p10's "invisible design" ideal ("redirect attention to the app's
purpose, don't catch it") argues even the logo should be quiet in a daily tool.

---

## 4. Layout — where space is spent wrong

### 4.1 The Overview three-column cram
At the default width the 3-column Overview (Incoming | Outgoing | right-rail) is
fine, but it has no graceful narrow state: at the 1160px minimum the "Outgoing"
header **truncates to "Outg"** and the column captions (`Due`/`Pr`/`Added`)
collide with the total (visible in the min-scale capture). Filipiuk p33: elements
crammed until they overlap read as broken. A dashboard that can't survive its own
minimum window is a layout that only works at one size.

### 4.2 Content still touches structure
Filipiuk p235 is a rule I'm partly violating: *"text should never touch the
borders of the screen… most elements should stay away from the corners."* The
1100 reading column gives the *page* margins, but inside it, ledger rows run
edge-to-edge of the column and the right-rail content on Overview butts the window
frame. The breathing room is at the page level but not always at the block level.

### 4.3 Whitespace is rationed, not spent
This is the deep one, and it's where Notion is a different species. Filipiuk
devotes a whole chapter (p223–233) to the argument that **whitespace is the
mechanism, not the leftover** — p227: *"the less elements are on the screen, the
more the user focuses on the elements that are on the screen,"* and p229:
*"whitespace should not be filled without a good reason."* This app's instinct is
the opposite: fill the row, fill the width, pack the tiles. Even after the block
work, line-heights are tight, rows are 32px, sections are 24px apart. It reads as
efficient; it does not read as calm. For a tool you sit with, calm compounds.

### 4.4 Tap/click targets and click-to-edit discoverability
- Ledger amounts and names are **click-to-edit**, but at rest they look like plain
  text — no affordance until hover (Filipiuk p281: a clickable thing must *look*
  clickable; p132: give small interactive elements a tap area ≥44px). A
  first-return user doesn't know the numbers are editable.
- The row action glyphs are now hover-only (correct), but that means the entire
  action surface is invisible at rest — good for calm, but combined with
  invisible click-to-edit, a *lot* of this UI is undiscoverable until you already
  know it's there. That's fine for the author; it's a wall for anyone else,
  including the author in six months (Henderson p80 #6, recognition-over-recall).

---

## 5. Design choices — consistency and states

### 5.1 Type scale is better but still busy
The scale is now 11/14/16/20/30 — but the *body* of the app still mixes 10, 11,
12, 13 in practice (chart labels 9–10, hints 10–11, row text 13, headings 16).
Filipiuk's typography chapter wants a *small* set of steps used consistently; the
app has a defined scale and then a scatter of one-off sizes around it.

### 5.2 Three button vocabularies, still
`_button()` factory, `_btn()` inside dialogs, and `Clickable` labels acting as
buttons. Filled, line, and text-link styles (Filipiuk p130) are all present, but
not *mapped to a hierarchy* — a primary "Save" and a tertiary "+ Add item" and a
"Set budgets…" link don't follow the p131 rule ("the more important the button,
the more it stands out"). They differ by accident of which helper built them.

### 5.3 Missing states
Filipiuk p133: design default / hover / clicked / **disabled**. The app has hover;
it has almost no disabled or pressed states, and no skeleton/loading state (the
product register wants skeletons, not spinners). "Sync now" with no key does
nothing visible; a disabled state would say why.

### 5.4 Corner radius vs "user-friendly"
Filipiuk p132 is worth quoting against the brand: *"Sharp buttons with very low
corner radius (or just 0) feel more elegant and professional. More rounded buttons
are more user-friendly, and better for the eye."* The app moved 0→3px this
session — a good start, but 3px is still firmly on the "elegant/professional" (=
cooler, less friendly) end. If the goal word is **user-friendly** (it's in the
request), the radius wants to be 4–6px, which is exactly where Notion sits.

---

## 6. Notion's design language — the deep read

Notion is not "minimal because empty." It's a specific, teachable system. What it
gets right, and *why* each works:

**1. Everything is a block, and a block has no chrome.**
A heading, a paragraph, a table, a toggle — all the same primitive: content, a
hover-only left gutter (drag handle + `+`), and vertical rhythm. No borders, no
fills, no cards. Grouping comes entirely from **proximity and whitespace**
(Filipiuk p33). This is why a Notion page with 30 blocks feels calmer than this
app's page with 8 cards: the cards announce themselves; the blocks don't.

**2. Whitespace is the primary structuring device.**
Notion runs generous line-height (~1.5), roomy block spacing, and a wide left
margin. Nothing touches an edge (Filipiuk p235). The emptiness *is* the design
(p227) — it's what lets a dense database and a paragraph of text coexist without
either shouting.

**3. Monochrome first; colour is a rare, quiet guest.**
Notion's default surface is near-monochrome — warm near-black ink on off-white,
grey for secondary. Colour appears only as **muted, low-saturation tints** on
tags and callouts, never as a saturated fill behind primary content. When
everything is grey, the one coloured tag actually reads (Henderson p118). This is
the direct antidote to §3.1 here — Notion would never put a green fill behind a
green number.

**4. Actions are hidden until hover; the resting state is pure content.**
The `+`, the drag handle, the `⋯` menu, the block-type controls — all appear only
on hover. At rest a Notion page is *just what you wrote*. This is the "invisible
design" of Filipiuk p10 made literal: the chrome exists but stays out of sight
until you reach for it. (This app now does this for row glyphs — the lesson is to
extend it everywhere.)

**5. One typeface, few sizes, consistent weight.**
Notion uses one sans, a tight set of sizes, and leans on **weight and colour**
(bold, grey) for hierarchy rather than many sizes. Fewer type decisions = less
visual noise (Filipiuk typography chapter; Henderson p80 #4 consistency).

**6. Hairlines only where a boundary carries information.**
Notion *does* use borders — but almost only as **single hairline row-separators in
tables/databases**, never as boxes around things. A 1px divider between rows is
information (this row ends); a box around every row is noise. The app inverts
this: boxes around panels/cells, few clean row-dividers.

**7. Small rounded corners = approachable, not clinical.**
4–6px radius on inputs, buttons, hovers, menus. Enough to feel humane (Filipiuk
p132 "more user-friendly"), not so much it's bubbly. It signals "you can touch
this" without a border.

**8. Progressive disclosure via toggles.**
Complexity lives inside toggles and peek panels, not on the surface (Henderson
p100 accordion, p77 "leverage progressive disclosure"). The page shows the 20% you
need; the 80% is one click away. This app front-loads everything.

**9. Calm, human microcopy.**
Notion's empty states teach ("Type '/' for commands"); its labels are plain
(Filipiuk p253 "sound as human as possible"). This app's empty states are decent
but its labels still leak jargon ("P&L", "Pr", "ISO weeks (Mon–Sun,
cross-month)").

---

## 7. Applying Notion here — concrete, per surface

Ordered by how much noise each removes:

1. **Subscriptions calendar → borderless month.** Drop the 42 cell borders. Keep
   at most a faint hairline between week-rows (Notion table style, §6.6); put the
   day number small in the top-left; show colour only on days with an event. This
   single change removes ~40 rectangles of noise from the busiest page.

2. **Inputs → fill, not box.** Give `QLineEdit`/combos a `BG_INPUT` fill and **no
   resting border**; add the 1px `FOCUS` border only on `:focus`. The field reads
   as editable by being lighter than the page (Notion, §6.3), and focus becomes a
   real state-change on a calm base (Filipiuk p133).

3. **Kill the decorative colour fills.** `StatBox` Incoming/Outgoing → no green/red
   *fill*; keep the coloured number, drop the tinted rectangle. Tag chips → muted
   grey-tint pill, no border, coloured text only (Notion tags, §6.3). This is the
   biggest step toward "colour means something again" (§3.1).

4. **Chart de-ornament.** Gridlines to the faintest step (or none), thin the axis,
   drop ticks. Let the data line be the loudest ink on each chart (§3.2).

5. **Radius 3 → 5.** One token, whole-app warmth, directly serves the
   "user-friendly" goal (Filipiuk p132).

6. **Whitespace pass.** Bump line-height and block spacing ~15–20%; let content
   breathe. Explicitly *don't* refill the space you free (Filipiuk p229). This is
   the change that most makes it "feel like Notion" and least changes what's on
   screen.

7. **Standardise buttons to a 3-tier system** mapped to importance (filled primary
   / subtle secondary / text-link tertiary), one helper, retire `_btn` vs
   `_button` (Filipiuk p131; Henderson p80 #4).

8. **Make click-to-edit look editable.** A resting affordance on editable
   text/amounts (a faint underline-on-hover is not enough) so the interface is
   discoverable without prior knowledge (Filipiuk p281; Henderson p80 #6).

9. **Language pass.** "P&L" → "Net" or "Profit"; "Pr" → "Priority" (or an icon
   with a tooltip); rewrite "ISO weeks (Mon–Sun, cross-month)" in human terms
   (Filipiuk p253; Henderson p122 microcopy).

---

## 8. The honest tension

Two things in the brief pull against each other, and it's worth naming rather than
pretending they don't:

- **"Dense" (the app's stated identity) vs "user-friendly / Notion" (this
  request).** Notion's whole power is *low* density and high whitespace. You can't
  have terminal-density *and* Notion-calm on the same surface. The resolution
  Notion itself uses (§6.8): keep density *inside* a block (a table can be dense)
  and calm *between* blocks (the page breathes). Apply that split deliberately, or
  the two instincts will keep fighting in every screen.

- **"Invisible until hover" vs discoverability.** Notion gets away with hiding
  everything because it's a mass-market tool people learn once and use forever, and
  because "/" is a universal escape hatch. A private tool with no onboarding and
  hover-only affordances risks becoming unusable to its own author after a gap.
  The fix isn't more chrome — it's one discoverable escape hatch (the `Ctrl+K`
  palette already built) plus resting affordances on the *editing* actions, so the
  calm surface stays calm but the door handles are visible.

**Bottom line:** the app has done the hard structural half of becoming
Notion-like (blocks, text sidebar, consolidated actions). What remains is the
*subtractive* half — pulling out the borders, fills, and redundant colour that
still make it feel like a bordered dashboard wearing a Notion coat — and the
*spatial* half: actually spending the whitespace Notion's calm is made of.
