# Budgeting Tool

A personal finance desktop app built for one thing: keeping **the plan** and **the bank statement** honest against each other, in the same place, at the same standard.

## Aim

Most budgeting tools make you pick one of two views and treat the other as an afterthought — either a forecast you trust but never check against reality, or a bank-reconciled report that tells you what happened with no sense of what was supposed to happen. This app keeps both live at once:

- **The plan** — a recurring ledger of income, expenses, subscriptions, and shared costs — projects forward: what *should* happen this month, this quarter, this year.
- **The reality** — imported bank transactions, reconciled automatically against that plan — shows what *actually* happened.

Neither view is the "advanced mode" of the other. The Overview page answers "am I on track?" at a glance; Analytics, History, and Subscriptions provide enough density to trust the number when it says no.

## Who it's for

A single person managing their own finances — recurring bills, a few shared subscriptions with housemates or family, savings goals, and a bank account to reconcile against. It is a personal tool, not a product: precise and information-dense rather than simplified, closer to a terminal than a consumer finance app.

## What it does

- **Recurring ledger** — income and expense items with flexible recurrence rules (weekly, monthly, custom intervals, specific days of month), due dates, and priorities.
- **Bank import & reconciliation** — import bank statements (CSV/OFX) and automatically categorize and match transactions against the plan.
- **Shared plans** — split subscriptions and costs with other people; track who owes what and settle up.
- **Savings goals** — target-based goals with linked expenses and a projected completion date.
- **Analytics** — budget-vs-actual, spending composition, cash-flow, net-worth history, liquid-balance forecasting, and month-over-month comparisons, laid out to minimize scrolling.
- **Subscriptions** — a renewal timeline and calendar view of recurring bills and due dates, with detection of untracked recurring bank charges.

## Tech

A PyQt6 desktop app (Windows). All charts are hand-drawn with `QPainter` — no charting library. Business logic (`backend.py`) is pure Python with no Qt dependency, so it's independently unit-tested (`tests/`). See [PRODUCT.md](PRODUCT.md) and [DESIGN.md](DESIGN.md) for the strategic and visual-design context, and [docs/cycle-editor-brief.md](docs/cycle-editor-brief.md) for a worked example of a past design decision.

## Running it

```
python main.py
```

Personal data lives in `data/` (gitignored) and is created on first run.
