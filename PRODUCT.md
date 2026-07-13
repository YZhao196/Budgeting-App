# Product

## Register

product

## Platform

web

## Users

A single person managing their own personal finances — recurring income and expenses, shared subscriptions with a small circle of people (housemates, family), savings goals, and bank-imported transactions. Not built for distribution; this is a personal tool used directly by its own author, at a desk, checking in regularly rather than glancing occasionally.

## Product Purpose

A budgeting tool that treats **planning** and **reality** as equally central, not one primary and one secondary. The recurring-item ledger (income/expenses, subscriptions, shared plans) projects forward — what should happen. Bank-imported transactions and the budget-vs-actual reconciliation show what actually happened. Success is a single glance at the Overview page answering "am I on track" without digging, and enough density elsewhere (Analytics, History, Subscriptions) to trust the number when it says no.

## Positioning

The plan and the bank statement live in the same tool and are held to the same standard — most budgeting apps make you choose between a forecast you trust and a reconciliation you trust; this one keeps both live at once.

## Brand Personality

Precise and no-nonsense, dense rather than simplified. The reference point is a terminal or trading-desk tool, not a consumer finance app — comfortable showing real complexity (recurrence rules, split shares, multi-account net worth) rather than smoothing it into a friendlier but vaguer summary. Bad news (a deficit, an overdue bill, negative net worth) is reported factually — color, label, and position together, never alarm chrome or apologetic copy.

## Anti-references

Explicitly not the rounded, colorful, friendly consumer-finance style of Mint, YNAB, or Monarch. No gradients, no soft shadows, no rounded corners, no decorative color. This should read as a tool, not a lifestyle app.

## Design Principles

Numbers lead; chrome doesn't compete with them. Every screen's first job is showing a number or a trend, not framing one.

Plan and reality are peers. The recurring ledger and the bank-reconciled view get equal visual weight and equal polish — neither is the "advanced" mode of the other.

Density is a feature, not a bug to fix. A power-user tool earns the right to show more at once, provided it stays scannable — this is a deliberate tradeoff against simplification.

Functional color only. Green/red/amber always encode a real state (income vs. expense, on-track vs. overdue) and are always paired with a label or position, never used decoratively or as the sole signal.

Calm under bad news. Deficits and overruns are reported plainly, in the same visual language as good news — no separate "alarm" treatment.

## Accessibility & Inclusion

Body text at ≥4.5:1 contrast against its background (already the working assumption behind `theme.py`'s `TEXT_MUTED`/`TEXT_DIM` tokens). Respect reduced-motion for the existing entry animations (`widgets.ANIMATE`). Red/expense and green/income are never the only signal — sign, label, and position (Incoming vs. Outgoing columns) always corroborate the color, since red/green is a common colorblind failure point.
