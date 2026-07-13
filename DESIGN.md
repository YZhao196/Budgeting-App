---
name: Budgeting Tool
description: A personal finance terminal — recurring plan and bank reality held to the same flat, exact standard.
colors:
  bg-app: "#111111"
  bg-sidebar: "#181818"
  bg-card: "#1e1e1e"
  bg-card-soft: "#242424"
  bg-hover: "#2c2c2c"
  bg-input: "#0e0e0e"
  bg-pill: "#303030"
  border: "#2c2c2c"
  border-soft: "#202020"
  border-light: "#383838"
  text: "#d4d4d4"
  text-muted: "#9a9a9a"
  text-dim: "#8a8a8a"
  income-green: "#5da876"
  income-green-bright: "#74c490"
  income-green-bg: "#192219"
  income-green-border: "#243824"
  expense-terracotta: "#b86060"
  expense-terracotta-bright: "#d07878"
  expense-terracotta-bg: "#221818"
  expense-terracotta-border: "#382424"
  warning-amber: "#c8944a"
  series-steel-blue: "#6b8fc4"
  series-muted-purple: "#7a68a8"
  series-teal: "#4aacac"
  series-copper: "#c47a5a"
  series-yellow-green: "#8ab060"
  on-accent: "#0d1a10"
typography:
  display:
    fontFamily: "Arial Nova Light, Arial, sans-serif"
    fontSize: "34px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "normal"
  headline:
    fontFamily: "Arial Nova, Arial, sans-serif"
    fontSize: "19px"
    fontWeight: 700
    lineHeight: 1.2
  title:
    fontFamily: "Arial Nova, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Arial Nova, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Arial Nova, Arial, sans-serif"
    fontSize: "9px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "1px"
rounded:
  none: "0px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "16px"
  xl: "20px"
components:
  button-primary:
    backgroundColor: "{colors.income-green-bg}"
    textColor: "{colors.income-green}"
    rounded: "{rounded.none}"
    padding: "6px 16px"
  button-primary-hover:
    backgroundColor: "{colors.income-green-bg}"
    textColor: "{colors.income-green}"
  button-secondary:
    backgroundColor: "{colors.bg-input}"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.none}"
    padding: "6px 16px"
  card:
    backgroundColor: "{colors.bg-card}"
    textColor: "{colors.text}"
    rounded: "{rounded.none}"
    padding: "16px 14px"
  input:
    backgroundColor: "{colors.bg-input}"
    textColor: "{colors.text}"
    rounded: "{rounded.none}"
    padding: "6px 9px"
  stat-box-income:
    backgroundColor: "{colors.income-green-bg}"
    textColor: "{colors.income-green}"
    rounded: "{rounded.none}"
    padding: "9px 12px"
  stat-box-expense:
    backgroundColor: "{colors.expense-terracotta-bg}"
    textColor: "{colors.expense-terracotta}"
    rounded: "{rounded.none}"
    padding: "9px 12px"
---

# Design System: Budgeting Tool

## 1. Overview

**Creative North Star: "The Trading Terminal"**

This is a desk tool, not a lifestyle app. Every screen is a readout: numbers first, chrome second, nothing between the user and the figure they came to check. The palette is deliberately restrained — desaturated sage green, terracotta, and amber sit on near-black, saturated only where a single number needs to earn attention (the hero P&L value). Depth comes from stepped tone, not shadow; corners are square throughout. The system explicitly rejects the rounded, colorful, friendly grammar of consumer finance apps (Mint, YNAB, Monarch) — this should never look like it's trying to be liked.

Two views are held to equal visual weight by design: the recurring plan (what should happen) and the bank-reconciled reality (what did happen). Neither gets softer treatment or more decoration than the other; the system's job is to make both trustworthy at a glance.

**Key Characteristics:**
- Flat, zero-radius surfaces stepped by tone, not shadow
- Muted, functional color — never decorative, always paired with a label or position
- One saturated moment per screen (the hero P&L number), everything else restrained
- Dense information layout; no simplification for its own sake
- Hairline 1px borders throughout; hover states brighten border color, nothing glows

## 2. Colors

Restrained and confident — a small, muted palette that reports state rather than decorating it, with saturation spent only where a single figure needs to lead the screen.

### Primary
- **Income Green** (`#5da876`): income amounts, positive P&L, "on track" states, the Incoming ledger column, checked/active chip fills.
- **Income Green Bright** (`#74c490`): the one saturated moment in the system — the hero P&L number on the Overview slab, and the net-worth line. Reserved for headline figures only.

### Secondary
- **Expense Terracotta** (`#b86060`): expense amounts, negative P&L, the Outgoing ledger column, overdue/overrun states.
- **Expense Terracotta Bright** (`#d07878`): emphasis variant for deficit banners and hover states on expense rows.

### Tertiary
- **Warning Amber** (`#c8944a`): due-soon states, budget-pace amber zone (85–100% of target), priority-soon dots. Sits between green and terracotta on the urgency scale and is never used for anything else.

### Neutral
- **App Black** (`#111111`): base window background — the darkest surface in the system.
- **Sidebar Ink** (`#181818`): navigation rail and top bar, one step above app black.
- **Card Charcoal** (`#1e1e1e`): the standard panel/card surface — everything the user reads sits here.
- **Card Soft** (`#242424`): nested rows, sub-boxes, metric tiles — one step above a card, for content living inside a card.
- **Hover Graphite** (`#2c2c2c`): row and button hover fill; doubles as the default hairline border color.
- **Input Void** (`#0e0e0e`): editable fields — darker than the card that contains them, so an editable region always reads as a "hole" to fill.
- **Primary Text** (`#d4d4d4`): body copy and figures.
- **Muted Text** (`#9a9a9a`): secondary labels, ≥4.5:1 against card surfaces by design.
- **Dim Text** (`#8a8a8a`): tertiary text — dates, hints, the least important label on a row.

### Named Rules
**The One Saturated Moment Rule.** Every other green in the system is the muted `#5da876`. Only the hero P&L figure and the net-worth headline get the brighter `#74c490` — its rarity is what makes it read as "the number that matters most on this screen."

**The Color-Plus Rule.** Green and terracotta never stand alone as the only signal. A ledger row's sign, its column (Incoming vs. Outgoing), and its color always agree — color is corroboration, never the sole carrier of meaning.

## 3. Typography

**UI Font:** Arial Nova (regular weight, all standard text)
**Display Font:** Arial Nova Light (large numbers only, ≥18px)

**Character:** One family in two weights, not a pairing — Arial Nova Light exists solely to let large figures (the hero P&L, metric-tile values) sit lighter and bigger without ever feeling decorative. Everything else stays in regular weight Arial Nova, deliberately plain.

### Hierarchy
- **Display** (700, 34px, 1.1 line-height): the single hero P&L figure on the Overview slab. The only place font weight and size are used to shout.
- **Headline** (700, 19px, 1.2): metric-tile values, dialog titles — the second tier of "this number matters."
- **Title** (700, 14px, 1.3): card and section headers ("P&L — Last 5 months", dialog headings).
- **Body** (400, 12px, 1.4): standard row labels, amounts, form fields — the working default for nearly everything on screen.
- **Label** (700, 9px, 1.2, 1px letter-spacing, uppercase where used): section eyebrows like "WEEKLY P&L", tab captions — the smallest, driest tier.

### Named Rules
**The No-Ornament Rule.** Weight and size carry all hierarchy. No italics, no color-as-emphasis on body text, no decorative type anywhere in the system.

## 4. Elevation

Flat by tonal layering, never shadow. Depth is conveyed purely by stepping background lightness — `#111111` → `#1e1e1e` → `#242424` → `#2c2c2c` — each step signaling "this sits on top of that," paired with a 1px hairline border (`#2c2c2c` default, `#202020` for a quieter internal divider, `#383838` on hover or focus). No `box-shadow` appears anywhere in the system.

### Named Rules
**The Flat-By-Default Rule.** Nothing lifts off the surface. A card is a tone step and a hairline border, full stop — never a shadow, never a glow, never on hover either.

## 5. Components

Tactile and exact: every control is a flat rectangle with a hairline border, and the only thing that happens on hover is the border brightening from `#2c2c2c`/`#383838` toward the text or accent color. Nothing glows, lifts, or scales.

### Buttons
- **Shape:** flat rectangle, 0px radius always.
- **Primary** (save / add / confirm): `#192219` background, `#5da876` text, `#243824` border, `6px 16px` padding.
- **Secondary** (cancel / neutral): `#0e0e0e` background, `#9a9a9a` text, `#2c2c2c` border.
- **Hover / Focus:** border color brightens to the text's own hue (e.g. primary's border brightens toward `#5da876`); no background or shadow change.
- **Danger** (remove / delete affordances): rendered as plain text (✕) that turns `#b86060` on hover, not a filled button — deletion is deliberately the least visually weighted action on a row.

### Chips (day-of-month pickers, weekday selectors)
- **Style:** `#0e0e0e` background, `#9a9a9a` text, `#2c2c2c` border, flat square, no radius.
- **State:** checked/selected fills solid `#5da876` (or `#c8944a` accent variants in context) with `#0d1a10` text for contrast — the one place a chip goes from outline to filled.

### Cards / Containers
- **Corner Style:** 0px radius, always.
- **Background:** `#1e1e1e` standard card; `#242424` for a tile nested inside a card.
- **Shadow Strategy:** none — see Elevation.
- **Border:** 1px solid `#202020` (soft internal) or `#2c2c2c` (default card edge).
- **Internal Padding:** `16px 14px` typical card margin, `13px 10px` for a compact metric tile.

### Inputs / Fields
- **Style:** `#0e0e0e` background (darker than its containing card), 1px `#2c2c2c` border, 0px radius, `6px 9px` padding.
- **Focus:** border brightens to `#74c490` (the Focus token) — the only focus treatment in the system, no glow ring.
- **Error / Disabled:** not yet a distinct treatment; disabled fields currently rely on dimmed text only.

### Navigation
- **Sidebar:** fixed 72px rail, `#181818` background, icon-only with active-tab accent underline in income green. No hover lift, only icon/label color shift.
- **Top bar:** 56px header, `#181818` background, month/period controls as flat pill buttons (`#303030` fill when active).
- **Tabs (SegTabBar):** flat pill or underline style depending on context; active state fills `#303030` or shows a green underline, inactive tabs sit at muted text color with no border.

### Charts (signature component)
Every chart in the system (P&L line, donut breakdown, budget-vs-actual bars, calendar heatmap, sankey, forecast band) is hand-painted with QPainter directly against these same tokens — no charting library, no default palette. Hover always draws a value pill in `#242424` with a `#383838` border, positioned to clamp inside the plot area. The 8-step `SERIES` palette (sage green, steel blue, amber, terracotta, muted purple, teal, copper, yellow-green) is reserved for multi-category breakdowns only; two-state data (income/expense, on/over budget) always uses the functional green/red/amber, never a SERIES color.

## 6. Do's and Don'ts

### Do:
- **Do** step depth with background tone (`#111111` → `#1e1e1e` → `#242424` → `#2c2c2c`) and a 1px border — never a shadow.
- **Do** keep every corner at 0px radius, on every component, with no exceptions.
- **Do** pair every green/red/amber signal with a label or position (column, sign, icon) — color is corroboration, never the only signal.
- **Do** reserve `#74c490` (income-green-bright) for the single hero figure on a screen; every other positive value uses the muted `#5da876`.
- **Do** treat hover as a border-color brighten only (`#2c2c2c`/`#383838` → the element's own hue) — no background shift, no shadow, no scale.
- **Do** default to dense, information-rich layouts; a power-user tool earns the right to show more at once.

### Don't:
- **Don't** use the rounded, colorful, friendly grammar of consumer finance apps like Mint, YNAB, or Monarch — no rounded corners, no gradients, no soft shadows, no decorative color, anywhere.
- **Don't** add `box-shadow` or any glow/lift effect to any component, at rest or on hover.
- **Don't** use a saturated or bright color as decoration — every color on screen must be reporting a real state (income, expense, warning, selection).
- **Don't** treat the recurring-plan view and the bank-reconciled view as primary/secondary — give both equal visual weight and equal polish.
- **Don't** simplify or hide complexity to make the UI feel friendlier — density is a deliberate choice, not a gap to close.
- **Don't** dress up bad news (a deficit, an overdue bill, negative net worth) with alarm-style chrome — report it in the same flat visual language as good news.
