# Brief: why the subscription cycle editor was incomplete

## Summary

The "Add / Edit subscription" dialog (`SharedPlanDialog` in `widgets.py`) let a
user pick a **billing cycle** (Weekly / Monthly / … / Yearly) but gave them **no
way to say _when_ that cycle lands** — which day a weekly bill falls on, or which
date a yearly bill renews. That information was silently invented by the caller,
so every subscription anchored to the same arbitrary date regardless of reality.

## Root cause

The recurrence engine is *anchor-relative*. A rule like
`{"type": "interval", "every": 1, "unit": "year"}` carries **no date of its own** —
`backend.occurrence_dates()` projects it forward from the item's `start` field
(see `test_occ_yearly`: a yearly rule fires on the anniversary of `start`; a
weekly rule steps 7 days from `start`).

But the dialog never collected a `start`. Instead `main.py._add_subscription`
hard-coded:

```python
start = f"{self.year:04d}-{self.month:02d}-01"   # 1st of the month you're viewing
```

Consequences:

1. **No anchor control.** A yearly subscription always renewed on the **1st of
   whatever month happened to be on screen** when you clicked "Add". You could
   never say "renews 14 March". Weekly subs anchored to that 1st too, so the
   weekday was accidental.
2. **View-dependent, non-reproducible data.** The same subscription got a
   different renewal date depending on which month you were browsing at creation
   time — a hidden dependency between UI navigation state and stored data.
3. **Editing couldn't fix it.** `update_subscription` didn't accept a `start`
   argument at all, so even re-opening the item gave no way to correct the anchor.
4. **Dropdown ordering.** `_CYCLES` listed the options
   Monthly → Quarterly → 6-months → Yearly → **Weekly**, with Weekly stranded at
   the bottom instead of leading the ascending sequence — a small but real
   read-order papercut.

The only anchor a user *could* influence was the "Specific days of month" rule
(`{"type": "days", "days": [...]}`), which stores its own days and ignores
`start` — the one path that happened to sidestep the missing field, which is
probably why the gap went unnoticed.

## Fix shipped

- **Reordered `_CYCLES`** to ascending period: Weekly → Monthly → Quarterly →
  Every 6 months → Yearly. New subscriptions default to **Monthly**.
- **Added a `DateField` widget** — an on-theme calendar popup reusing the same
  `_calendar_qss()` / `QCalendarWidget` styling as the ledger's due-date picker —
  surfaced in the dialog as **"First billing date"**. It sets the item's `start`,
  i.e. the real recurrence anchor. A contextual hint updates live
  ("Renews every year on 14 Mar", "Renews every Tuesday", …).
- **Threaded the date through** create *and* edit: `SharedPlanDialog._save`
  returns `start`; `main.py._add_subscription` uses it (falling back to the old
  1st-of-month default only if absent); `update_subscription` now accepts and
  persists `start` so an existing subscription's anchor can be corrected.
- The date field is hidden for the "Specific days of month" cycle, which carries
  its own anchor.

## Still worth considering (not in this change)

- **End date / cancellation date** for fixed-term plans (the `end` field exists
  in the model but has no editor here).
- **"Every N weeks/months"** arbitrary intervals — the engine supports `every: N`
  but the dialog only exposes the fixed presets.
- **Timezone / month-end semantics** — a start of the 31st on a monthly cycle
  needs a defined rule for short months; verify `occurrence_dates` behaviour and
  surface it to the user.
