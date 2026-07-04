"""Pure calculation helpers – no Qt in here.

Everything the UI needs to *display* is derived from the raw month document:
category roll-ups, totals, profit & loss, savings rate, due-date priority and
the multi-month history that feeds the dashboard chart.
"""

from __future__ import annotations

import calendar as _cal
import re as _re
from datetime import date, timedelta

import datamanagement as dm


# --------------------------------------------------------------------------- #
#  Category amounts (parents are the sum of their children)
# --------------------------------------------------------------------------- #
def node_amount(node: dict) -> float:
    """The item's own planned amount (parents = sum of all children)."""
    if node.get("children"):
        return sum(node_amount(c) for c in node["children"])
    return float(node.get("amount", 0.0))


def total(nodes: list) -> float:
    return sum(node_amount(n) for n in nodes)


# --------------------------------------------------------------------------- #
#  Recurrence: does an item "fire" (count) in a given month?
# --------------------------------------------------------------------------- #
def fires_in(repeat: dict | None, year: int, month: int) -> bool:
    """True if a recurrence rule is due in (year, month).  Items with no rule
    (one-offs) are always considered active for the month they live in."""
    if not repeat:
        return True
    kind = repeat.get("type")
    if kind == "days":
        return True                                   # specific days → monthly
    if kind == "interval":
        unit = repeat.get("unit", "month")
        every = max(1, int(repeat.get("every", 1)))
        if unit in ("day", "week"):
            return True                               # sub-monthly → every month
        anchor = repeat.get("anchor")
        if anchor:
            ay, am = (int(x) for x in anchor.split("-"))
        else:
            ay, am = year, month                      # legacy/no anchor → fires now
        if unit == "month":
            diff = (year - ay) * 12 + (month - am)
            return diff >= 0 and diff % every == 0
        if unit == "year":
            return month == am and (year - ay) % every == 0
    return False  # unknown repeat type → don't include


def active_amount(node: dict, year: int, month: int) -> float:
    """Amount that counts toward (year, month): parents sum their *active*
    children; a leaf counts only if its recurrence fires this month."""
    if node.get("children"):
        return sum(active_amount(c, year, month) for c in node["children"])
    if fires_in(node.get("repeat"), year, month):
        return float(node.get("amount", 0.0))
    return 0.0


def active_total(nodes: list, year: int, month: int) -> float:
    return sum(active_amount(n, year, month) for n in nodes)


def recurring_total(nodes: list, year: int, month: int) -> float:
    """Active amount this month that comes from recurring (repeat-rule) leaves."""
    s = 0.0
    for n in nodes:
        if n.get("children"):
            s += recurring_total(n["children"], year, month)
        elif n.get("repeat") and fires_in(n.get("repeat"), year, month):
            s += float(n.get("amount", 0.0))
    return s


def _ym(doc: dict) -> tuple[int, int]:
    y, m = doc.get("month", "2026-01").split("-")
    return int(y), int(m)


def income_total(doc: dict) -> float:
    return active_total(doc.get("income", []), *_ym(doc))


# --------------------------------------------------------------------------- #
#  Predicted income — projects recurring income sources into future months
#  (mirrors datamanagement._carry's "only recurring items survive" rule,
#  but is read-only: it never touches disk).
# --------------------------------------------------------------------------- #
def _predicted_total(nodes: list, year: int, month: int) -> float:
    s = 0.0
    for n in nodes:
        if n.get("children"):
            s += _predicted_total(n["children"], year, month)
        elif n.get("recurring") and fires_in(n.get("repeat"), year, month):
            s += float(n.get("amount", 0.0))
    return s


def predicted_income_for_month(doc: dict, year: int, month: int) -> float:
    """Predicted income for an arbitrary (year, month) using this month's
    recurring income sources only (one-off income doesn't carry forward)."""
    return _predicted_total(doc.get("income", []), year, month)


def predicted_income_series(doc: dict, months_ahead: int = 6) -> list[dict]:
    """[{label, year, month, predicted}, ...] for the ``months_ahead`` months
    following the current one."""
    y, m = _ym(doc)
    out = []
    for i in range(1, months_ahead + 1):
        idx = y * 12 + (m - 1) + i
        py, pm = idx // 12, idx % 12 + 1
        out.append({
            "label":     dm.MONTH_ABBR[pm],
            "year":      py,
            "month":     pm,
            "predicted": predicted_income_for_month(doc, py, pm),
        })
    return out


def predicted_income_breakdown(doc: dict, year: int, month: int) -> list[tuple[str, float]]:
    """(name, amount) for every recurring income leaf active in (year, month)."""
    result: list[tuple[str, float]] = []
    def scan(nodes):
        for n in nodes:
            if n.get("children"):
                scan(n["children"])
            elif n.get("recurring") and fires_in(n.get("repeat"), year, month):
                result.append((n["name"], float(n.get("amount", 0.0))))
    scan(doc.get("income", []))
    return result


def expense_total(doc: dict) -> float:
    return active_total(doc.get("expenses", []), *_ym(doc))


def pnl(doc: dict) -> float:
    return income_total(doc) - expense_total(doc)


def savings_rate(doc: dict) -> float:
    inc = income_total(doc)
    return (pnl(doc) / inc) if inc else 0.0


# --------------------------------------------------------------------------- #
#  Due-date priority  ->  coloured dot
# --------------------------------------------------------------------------- #
PRIORITY_NONE, PRIORITY_OK, PRIORITY_SOON, PRIORITY_OVERDUE = range(4)

SOON_WINDOW_DAYS = 14


def _parse_due(due: str | None, today: date) -> date | None:
    if not due:
        return None
    try:
        if len(due) >= 10:              # ISO: YYYY-MM-DD
            from datetime import datetime
            return datetime.strptime(due[:10], "%Y-%m-%d").date()
        mm, dd = (int(x) for x in due.split("-"))   # legacy: MM-DD
        return date(today.year, mm, dd)
    except (ValueError, TypeError):
        return None


def priority(node: dict, today: date | None = None) -> int:
    """Classify an expense by how urgent its payment is."""
    today = today or date.today()
    if node.get("paid"):
        return PRIORITY_OK
    due = _parse_due(node.get("due"), today)
    if due is None:
        return PRIORITY_NONE
    delta = (due - today).days
    if delta < 0:
        return PRIORITY_OVERDUE
    if delta <= SOON_WINDOW_DAYS:
        return PRIORITY_SOON
    return PRIORITY_OK


# --------------------------------------------------------------------------- #
#  Weekly budget breakdown — actual bills by week
# --------------------------------------------------------------------------- #
def month_week_ranges(year: int, month: int, n_weeks: int) -> list[tuple[int, date, date]]:
    """Return (1-based week_num, start_date, end_date) for each configured week.
    Weeks are 7-day chunks from the 1st; the final chunk runs to month-end."""
    first = date(year, month, 1)
    last  = date(year, month, _cal.monthrange(year, month)[1])
    out   = []
    for w in range(n_weeks):
        start = first + timedelta(days=w * 7)
        if start > last:
            break
        is_last = (w == n_weeks - 1)
        end = last if is_last else min(start + timedelta(days=6), last)
        out.append((w + 1, start, end))
    return out


def _node_week_date(n: dict, year: int, month: int) -> "date | None":
    """Convert an item's added date (MM-DD) to a date in (year, month).
    The day component determines which week the item belongs to."""
    import calendar as _cal
    added = n.get("added")
    if added:
        try:
            day = int(str(added).split("-")[-1])
            day = min(day, _cal.monthrange(year, month)[1])
            return date(year, month, day)
        except (ValueError, IndexError):
            pass
    return None


def bills_in_range(doc: dict, start: date, end: date) -> list[tuple[str, float]]:
    """(name, amount) for every leaf expense whose added date falls in [start, end]."""
    year, month = start.year, start.month
    result: list[tuple[str, float]] = []
    def scan(nodes):
        for n in nodes:
            if n.get("children"):
                scan(n["children"])
            else:
                d = _node_week_date(n, year, month)
                if d and start <= d <= end:
                    result.append((n["name"], float(n.get("amount", 0.0))))
    scan(doc.get("expenses", []))
    return result


def income_in_week(doc: dict, start: date, end: date) -> float:
    """Sum of income leaf amounts whose added date falls in [start, end]."""
    year, month = start.year, start.month
    total = 0.0
    def scan(nodes):
        nonlocal total
        for n in nodes:
            if n.get("children"):
                scan(n["children"])
            else:
                d = _node_week_date(n, year, month)
                if d and start <= d <= end:
                    total += float(n.get("amount", 0.0))
    scan(doc.get("income", []))
    return total


def spend_by_tag(items: list, rstart: date, rend: date) -> list[tuple[str, float]]:
    """Total expense per tag in the range (an item with several tags counts
    toward each; untagged spend is bucketed under '(untagged)').  Sorted desc."""
    res: dict = {}
    for defn, _ in _iter_leaf_defs(items):
        if defn.get("type") != "expense":
            continue
        amt = 0.0
        for d in occurrence_dates(defn, rstart, rend):
            e = _effective(defn, d)
            if e:
                amt += e["amount"]
        if amt == 0:
            continue
        tags = defn.get("tags") or []
        if tags:
            for t in tags:
                res[t] = res.get(t, 0.0) + amt
        else:
            res["(untagged)"] = res.get("(untagged)", 0.0) + amt
    return sorted(res.items(), key=lambda kv: -kv[1])


def bills_summary(items: list, rstart: date, rend: date, today: date) -> dict:
    """Paid / unpaid / overdue stats for dated expense bills firing in the range
    (drives the 'bills due this week' strip)."""
    due_total = paid_total = 0.0
    due_count = overdue = paid_count = 0
    for i in instances_in_range(items, rstart, rend):
        if i["type"] != "expense" or not i.get("due"):
            continue
        if i.get("paid"):
            paid_total += i["amount"]; paid_count += 1
        else:
            due_total += i["amount"]; due_count += 1
            d = _parse_due(i["due"], today)
            if d and d < today:
                overdue += 1
    return {"due_total": due_total, "due_count": due_count, "overdue": overdue,
            "paid_total": paid_total, "paid_count": paid_count}


def _undated_expense_total(doc: dict) -> float:
    """Sum of leaf expense nodes that carry no due date (variable / discretionary)."""
    total = 0.0
    def scan(nodes):
        nonlocal total
        for n in nodes:
            if n.get("children"):
                scan(n["children"])
            elif not n.get("due"):
                total += float(n.get("amount", 0.0))
    scan(doc.get("expenses", []))
    return total


def weekly_budgets(doc: dict) -> dict:
    """Per-week breakdown: fixed bills (by due date) + discretionary budget."""
    weekly  = float(doc.get("weekly_budget", 0.0))
    n_weeks = int(doc.get("weeks", 4))
    y, m    = _ym(doc)
    ranges  = month_week_ranges(y, m, n_weeks)
    rows = []
    for wk, start, end in ranges:
        bills = bills_in_range(doc, start, end)
        rows.append({
            "week":        wk,
            "start":       start,
            "end":         end,
            "budget":      weekly,
            "bills":       bills,
            "bills_total": sum(a for _, a in bills),
        })
    return {
        "weekly":       weekly,
        "weeks":        len(rows),
        "total_budget": weekly * len(rows),
        "rows":         rows,
    }


# --------------------------------------------------------------------------- #
#  Multi-month history (dashboard line chart)
# --------------------------------------------------------------------------- #
def _step_back(year: int, month: int, n: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) - n
    return idx // 12, idx % 12 + 1


def history(manager: "dm.DataManager", year: int, month: int,
            count: int = 5) -> list[tuple[str, float, bool]]:
    """Return ``[(label, pnl, is_current), …]`` for the ``count`` months ending
    at ``(year, month)``.  Months with no data simply contribute 0."""
    out: list[tuple[str, float, bool]] = []
    for back in range(count - 1, -1, -1):
        y, m = _step_back(year, month, back)
        label = dm.MONTH_ABBR[m]
        value = 0.0
        if manager.has_month(y, m):
            value = pnl(manager.load_month(y, m))
        out.append((label, value, back == 0))
    return out


# --------------------------------------------------------------------------- #
#  Period summary for the Weekly / Monthly / Yearly / YTD tabs
# --------------------------------------------------------------------------- #
def period_summary(manager: "dm.DataManager", year: int, month: int,
                   period: str, week_of_month: int | None = None) -> dict:
    """Aggregate income / expenses / P&L over the chosen period.

    * Weekly  – if week_of_month is given: dated bills in that week +
                1/n_weeks of undated expenses + 1/n_weeks of income.
                Otherwise falls back to dividing monthly totals evenly.
    * Monthly – the current month
    * Yearly  – every stored month in ``year``
    * YTD     – stored months in ``year`` up to and including ``month``
    """
    doc = manager.load_month(year, month)

    if period == "Monthly":
        inc, exp = income_total(doc), expense_total(doc)
        label = f"{dm.MONTH_NAMES[month]} {year}"
    elif period == "Weekly":
        n_weeks = max(1, int(doc.get("weeks", 4)))
        ranges  = month_week_ranges(year, month, n_weeks)
        inc_mo  = income_total(doc)
        if week_of_month is not None and 1 <= week_of_month <= len(ranges):
            _, start, end = ranges[week_of_month - 1]
            exp   = sum(a for _, a in bills_in_range(doc, start, end))
            inc   = income_in_week(doc, start, end)
            mn    = dm.MONTH_ABBR[month]
            label = f"Week {week_of_month} · {mn} {start.day}–{end.day}"
        else:
            inc   = inc_mo / n_weeks
            exp   = expense_total(doc) / n_weeks
            label = f"avg week · {dm.MONTH_NAMES[month]}"
    else:  # Yearly / YTD
        inc = exp = 0.0
        for y, m in manager.list_months():
            if y != year:
                continue
            if period == "YTD" and m > month:
                continue
            d = manager.load_month(y, m)
            inc += income_total(d)
            exp += expense_total(d)
        label = f"{period} {year}"

    return {"label": label, "income": inc, "expenses": exp, "pnl": inc - exp}


# =========================================================================== #
#  FLAT-STORE MODEL (3a) — occurrence engine + range aggregations + lenses
#
#  Items are stored once as *definitions* (a start date + optional recurrence +
#  per-occurrence overrides).  Any view — a month, an ISO week, a custom range —
#  is produced by *expanding* the definitions into concrete dated instances for
#  that range.  This keeps the model independent of month boundaries so weeks can
#  flow across them.
# =========================================================================== #
def _parse_iso(s: str | None) -> "date | None":
    if not s:
        return None
    try:
        from datetime import datetime
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _add_months(d: date, n: int) -> date:
    """Shift a date by n months, clamping the day to the target month length."""
    idx = d.year * 12 + (d.month - 1) + n
    y, m = idx // 12, idx % 12 + 1
    last = _cal.monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


def occurrence_dates(defn: dict, rstart: date, rend: date) -> list[date]:
    """Every date in [rstart, rend] on which ``defn`` fires, bounded by the
    definition's own start/end and its recurrence rule."""
    s = _parse_iso(defn.get("start"))
    if s is None:
        return []
    e = _parse_iso(defn.get("end"))
    hi = rend if e is None else min(rend, e)
    if s > hi:
        return []
    rec = defn.get("recurrence")
    out: list[date] = []

    if not rec:                                   # one-off on its start date
        if rstart <= s <= hi:
            out.append(s)
        return out

    rtype = rec.get("type")
    if rtype == "interval":
        unit  = rec.get("unit", "month")
        every = max(1, int(rec.get("every", 1)))
        if unit in ("day", "week"):
            step = every * (7 if unit == "week" else 1)
            if rstart <= s:
                d = s
            else:                                 # jump straight to the first in-range hit
                k = ((rstart - s).days + step - 1) // step
                d = s + timedelta(days=k * step)
            while d <= hi:
                out.append(d)
                d = d + timedelta(days=step)
        elif unit in ("month", "year"):
            stride = every * (12 if unit == "year" else 1)
            d = s
            while d < rstart and d <= hi:
                d = _add_months(d, stride)
            while d <= hi:
                if d >= rstart:
                    out.append(d)
                d = _add_months(d, stride)
    elif rtype == "days":                         # specific days of every month
        days = rec.get("days") or [s.day]
        anchor = max(s, rstart)
        cur = date(anchor.year, anchor.month, 1)
        endm = date(hi.year, hi.month, 1)
        while cur <= endm:
            last = _cal.monthrange(cur.year, cur.month)[1]
            for dd in sorted(set(int(x) for x in days)):
                occ = date(cur.year, cur.month, min(dd, last))
                if s <= occ <= hi and rstart <= occ <= rend:
                    out.append(occ)
            cur = _add_months(cur, 1)
    return sorted(out)


def _iter_leaf_defs(items: list, depth: int = 0):
    """Yield (leaf_definition, depth) for every leaf in the definition tree."""
    for n in items:
        if n.get("children"):
            yield from _iter_leaf_defs(n["children"], depth + 1)
        else:
            yield n, depth


def _effective(defn: dict, d: date) -> dict | None:
    """Apply the per-occurrence override for date ``d`` (None if skipped)."""
    ov = (defn.get("overrides") or {}).get(d.isoformat(), {})
    if ov.get("skipped"):
        return None
    gross = float(ov.get("amount", defn.get("amount", 0.0)))
    amount = gross
    # A shared *expense* you split only costs you your own share: deduct what
    # the other payers contribute so P&L / the ledger reflect your true
    # out-of-pocket cost rather than the full provider charge.
    if defn.get("shared") and defn.get("type") == "expense":
        member_total = sum(r["share"] for r in member_shares(defn, d))
        amount = gross - member_total
    return {
        "def_id":   defn.get("id"),
        "occ_date": d,
        "name":     defn.get("name"),
        "type":     defn.get("type"),
        "amount":   amount,
        "gross":    gross,
        "due":      ov.get("due", defn.get("due")),
        "paid":     bool(ov.get("paid", False)),
        "priority": ov.get("priority", defn.get("priority", 0)),
    }


def instances_in_range(items: list, rstart: date, rend: date) -> list[dict]:
    """Flatten the definition tree into concrete dated instances for the range."""
    out: list[dict] = []
    for defn, depth in _iter_leaf_defs(items):
        for d in occurrence_dates(defn, rstart, rend):
            inst = _effective(defn, d)
            if inst is not None:
                inst["depth"] = depth
                out.append(inst)
    return out


def totals_in_range(items: list, rstart: date, rend: date) -> dict:
    """Income / expense / P&L / savings-rate for everything firing in the range."""
    inc = exp = 0.0
    for inst in instances_in_range(items, rstart, rend):
        if inst["type"] == "income":
            inc += inst["amount"]
        else:
            exp += inst["amount"]
    return {"income": inc, "expenses": exp, "pnl": inc - exp,
            "savings_rate": (inc - exp) / inc if inc else 0.0}


# --------------------------------------------------------------------------- #
#  Shared plans — split a subscription / client deal across members, track who
#  has paid, and gate "shipping" until everyone has.
# --------------------------------------------------------------------------- #
def member_shares(defn: dict, occ_date: date) -> list[dict]:
    """Per-member breakdown for one occurrence of a *shared* plan.
    Returns [{name, share, paid}] (empty for non-shared or skipped occurrences).

    Even split divides the occurrence amount across the members, plus the owner
    too when ``owner_pays`` is set.  Custom split uses each member's own ``share``.
    Per-occurrence ``member_paid`` overrides mark who has paid."""
    shared = defn.get("shared")
    if not shared:
        return []
    ov = (defn.get("overrides") or {}).get(occ_date.isoformat(), {})
    if ov.get("skipped"):
        return []
    members = shared.get("members") or []
    if not members:
        return []
    amount   = float(ov.get("amount", defn.get("amount", 0.0)))
    paid_map = ov.get("member_paid", {})
    rows: list[dict] = []
    if shared.get("split") == "custom":
        for m in members:
            rows.append({"name": m.get("name"),
                         "share": float(m.get("share", 0.0)),
                         "paid": bool(paid_map.get(m.get("name"), False))})
    else:                                      # even
        heads = len(members) + (1 if shared.get("owner_pays") else 0)
        per = (amount / heads) if heads else 0.0
        for m in members:
            rows.append({"name": m.get("name"), "share": per,
                         "paid": bool(paid_map.get(m.get("name"), False))})
    return rows


def all_paid(defn: dict, occ_date: date) -> bool:
    """The 'ready-to-ship' gate: True only when every member of a shared plan
    has paid for this occurrence (False if there are no members)."""
    rows = member_shares(defn, occ_date)
    return bool(rows) and all(r["paid"] for r in rows)


def who_owes(items: list, start: date, end: date) -> list[dict]:
    """Aggregate every member across all shared plans firing in [start, end].
    Returns [{member, plans:[names], total, paid, owes}]."""
    agg: dict = {}
    for defn in items:
        if not defn.get("shared"):
            continue
        for d in occurrence_dates(defn, start, end):
            for r in member_shares(defn, d):
                a = agg.setdefault(r["name"],
                                   {"plans": set(), "total": 0.0, "paid": 0.0})
                a["plans"].add(defn.get("name"))
                a["total"] += r["share"]
                if r["paid"]:
                    a["paid"] += r["share"]
    out = []
    for name, a in sorted(agg.items()):
        out.append({"member": name, "plans": sorted(a["plans"]),
                    "total": a["total"], "paid": a["paid"],
                    "owes": a["total"] - a["paid"]})
    return out


def plan_summary(defn: dict, occ_date: date) -> dict:
    """Money breakdown for one occurrence of a shared plan.

    ``total`` is the full amount (what you pay a provider, or bill a client).
    For a *cost you split* (expense): ``your_net`` is what you actually bear
    (total minus the members' shares), ``recovered`` is what members have paid
    back, ``outstanding`` is still owed to you.  For *income* the same fields
    describe how much of the billed total clients have settled."""
    rows = member_shares(defn, occ_date)
    total        = float(defn.get("amount", 0.0))
    member_total = sum(r["share"] for r in rows)
    recovered    = sum(r["share"] for r in rows if r["paid"])
    unpaid       = [r["name"] for r in rows if not r["paid"]]
    return {
        "rows":        rows,
        "total":       total,
        "member_total": member_total,
        "recovered":   recovered,
        "outstanding": member_total - recovered,
        "your_net":    total - member_total,     # your own share of a split cost
        "ready":       bool(rows) and not unpaid,
        "unpaid":      unpaid,
    }


def people_roster(items: list, start: date, end: date) -> list[dict]:
    """Every individual across all shared plans in [start, end], with a per-plan
    breakdown.  [{member, plans:[{name, share, paid, date}], total, paid, owes}]."""
    agg: dict = {}
    for defn in items:
        if not defn.get("shared"):
            continue
        for d in occurrence_dates(defn, start, end):
            for r in member_shares(defn, d):
                a = agg.setdefault(r["name"],
                                   {"plans": [], "total": 0.0, "paid": 0.0})
                a["plans"].append({"name": defn.get("name"), "share": r["share"],
                                   "paid": r["paid"], "date": d.isoformat(),
                                   "id": defn.get("id")})
                a["total"] += r["share"]
                if r["paid"]:
                    a["paid"] += r["share"]
    out = []
    for name, a in sorted(agg.items()):
        out.append({"member": name, "plans": a["plans"], "total": a["total"],
                    "paid": a["paid"], "owes": a["total"] - a["paid"]})
    return out


def next_occurrence(defn: dict, after: date) -> "date | None":
    """First occurrence on/after ``after`` (searches ~13 months ahead)."""
    occs = occurrence_dates(defn, after, _add_months(after, 13))
    return occs[0] if occs else None


def recurring_payments(items: list, today: date) -> list[dict]:
    """All recurring leaf items with their next due date, sorted by it.
    [{id, name, type, amount, recurrence, next, shared, subscription}]."""
    out = []
    for defn, _ in _iter_leaf_defs(items):
        rec = defn.get("recurrence")
        if not rec:
            continue
        nxt = next_occurrence(defn, today)
        out.append({
            "id":           defn.get("id"),
            "name":         defn.get("name"),
            "type":         defn.get("type"),
            "amount":       float(defn.get("amount", 0.0)),
            "recurrence":   rec,
            "next":         nxt.isoformat() if nxt else None,
            "shared":       bool(defn.get("shared")),
            "subscription": bool(defn.get("subscription")),
        })
    out.sort(key=lambda r: (r["next"] or "9999-99-99", r["name"]))
    return out


def search(store, query: str) -> list[dict]:
    """Global search across items, subscriptions, people, accounts and
    transactions. Returns [{kind, name, detail, target}] (target = page key)."""
    q = (query or "").strip().lower()
    if not q:
        return []
    out: list[dict] = []

    def scan(nodes):
        for n in nodes:
            name = n.get("name", "")
            hay = " ".join([name, n.get("note", "")] + (n.get("tags") or [])).lower()
            if q in hay:
                if n.get("shared") or n.get("subscription"):
                    kind, target = "Subscription", "subscriptions"
                else:
                    kind = "Income" if n.get("type") == "income" else "Expense"
                    target = "overview"
                out.append({"kind": kind, "name": name, "target": target,
                            "detail": " · ".join(n.get("tags") or [])})
            if n.get("children"):
                scan(n["children"])
    scan(store.items())

    for p in store.people():
        if q in p.get("name", "").lower():
            out.append({"kind": "Person", "name": p["name"], "detail": "",
                        "target": "subscriptions"})
    for a in store.accounts():
        if q in a.get("name", "").lower():
            out.append({"kind": "Account", "name": a["name"],
                        "detail": a.get("kind", ""), "target": "networth"})
    for t in store.transactions():
        if q in (t.get("description", "") or "").lower():
            out.append({"kind": "Transaction", "name": t.get("description", ""),
                        "detail": f"{t.get('date', '')}", "target": "settings"})
    return out[:60]


def upcoming_renewals(items: list, today: date, days: int = 14) -> list[dict]:
    """Subscriptions (shared or flagged) whose next occurrence is within ``days``.
    [{id, name, next, days_until, amount, type}] sorted by date."""
    out = []
    for defn in items:
        if not (defn.get("shared") or defn.get("subscription")):
            continue
        nxt = next_occurrence(defn, today)
        if not nxt:
            continue
        du = (nxt - today).days
        if 0 <= du <= days:
            out.append({"id": defn.get("id"), "name": defn.get("name"),
                        "next": nxt.isoformat(), "days_until": du,
                        "amount": float(defn.get("amount", 0.0)),
                        "type": defn.get("type")})
    out.sort(key=lambda r: r["next"])
    return out


# --------------------------------------------------------------------------- #
#  Net worth (accounts) + cash-flow forecast
# --------------------------------------------------------------------------- #
LIABILITY_KINDS = {"debt", "credit"}
LIQUID_KINDS = {"cash", "savings"}


def net_worth(accounts: list) -> dict:
    """{assets, liabilities, net} from a list of account dicts.
    Debt / credit accounts are liabilities; everything else is an asset."""
    assets = sum(float(a.get("balance", 0)) for a in accounts
                 if a.get("kind") not in LIABILITY_KINDS)
    liab = sum(float(a.get("balance", 0)) for a in accounts
               if a.get("kind") in LIABILITY_KINDS)
    return {"assets": assets, "liabilities": liab, "net": assets - liab}


def liquid_balance(accounts: list) -> float:
    """Cash + savings only — the starting point for a cash-flow forecast."""
    return sum(float(a.get("balance", 0)) for a in accounts
               if a.get("kind") in LIQUID_KINDS)


def forecast(items: list, start_balance: float, today: date,
             months: int = 6) -> list[dict]:
    """Project the liquid balance forward, applying each future month's recurring
    income minus expenses.  [{label, year, month, balance, pnl}]."""
    bal = float(start_balance)
    out = []
    base = today.year * 12 + (today.month - 1)
    for i in range(1, months + 1):
        idx = base + i
        fy, fm = idx // 12, idx % 12 + 1
        last = _cal.monthrange(fy, fm)[1]
        t = totals_in_range(items, date(fy, fm, 1), date(fy, fm, last))
        pnl = t["income"] - t["expenses"]
        bal += pnl
        out.append({"label": dm.MONTH_ABBR[fm], "year": fy, "month": fm,
                    "balance": bal, "pnl": pnl})
    return out


def monthly_equiv(amount: float, recurrence: dict | None) -> float:
    """Normalise a recurring amount to a per-month figure (for cross-cadence totals)."""
    if not recurrence or recurrence.get("type") != "interval":
        return float(amount)
    every = max(1, int(recurrence.get("every", 1)))
    per = {"day": 30.4375, "week": 4.345, "month": 1.0,
           "year": 1 / 12.0}.get(recurrence.get("unit", "month"), 1.0)
    return float(amount) * per / every


# --------------------------------------------------------------------------- #
#  Time lenses — every view is just a date range over the flat store
# --------------------------------------------------------------------------- #
def _iso_week_range(anchor: date) -> tuple[date, date]:
    start = anchor - timedelta(days=anchor.weekday())     # back to Monday
    return start, start + timedelta(days=6)


def _monday_in_month_range(anchor: date) -> tuple[date, date]:
    """Monday-aligned weeks that still reset at the 1st of the month."""
    first = date(anchor.year, anchor.month, 1)
    last  = date(anchor.year, anchor.month, _cal.monthrange(anchor.year, anchor.month)[1])
    # Monday on/before the anchor, but never before the 1st.
    start = anchor - timedelta(days=anchor.weekday())
    if start < first:
        start = first
    end = start + timedelta(days=(6 - start.weekday()))   # the following Sunday
    if end > last:
        end = last
    return start, end


def range_for_lens(lens: str, anchor: date) -> tuple[date, date, str]:
    """(start, end, label) for the period containing ``anchor`` under ``lens``."""
    if lens == "month":
        first = date(anchor.year, anchor.month, 1)
        last  = date(anchor.year, anchor.month, _cal.monthrange(anchor.year, anchor.month)[1])
        return first, last, f"{dm.MONTH_NAMES[anchor.month].upper()} {anchor.year}"
    if lens == "monday_in_month":
        s, e = _monday_in_month_range(anchor)
    else:                                              # "iso_week" (default)
        s, e = _iso_week_range(anchor)
    lab = (f"{dm.MONTH_ABBR[s.month]} {s.day}"
           f" – {dm.MONTH_ABBR[e.month]} {e.day}")
    return s, e, lab


def step_lens(lens: str, anchor: date, delta: int) -> date:
    """Move the anchor one period forward (+1) or back (-1) under ``lens``."""
    if lens == "month":
        return _add_months(date(anchor.year, anchor.month, 1), delta)
    if lens == "monday_in_month":
        s, _ = _monday_in_month_range(anchor)
        return s + timedelta(days=7 * delta)
    s, _ = _iso_week_range(anchor)                     # iso_week
    return s + timedelta(days=7 * delta)


# --------------------------------------------------------------------------- #
#  View builder — expand definitions into display nodes for a date range.
#  The returned nodes are intentionally ``cat``-shaped so the existing ledger
#  widgets render them unchanged.  Amounts are already resolved for the range
#  (recurring=False / repeat=None), so no recurrence re-interpretation happens
#  downstream; recurrence is surfaced separately via the ``_recur*`` fields.
# --------------------------------------------------------------------------- #
def _view_leaf(defn: dict, rstart: date, rend: date) -> dict | None:
    occs = occurrence_dates(defn, rstart, rend)
    eff  = [e for e in (_effective(defn, d) for d in occs) if e]
    if not eff:
        return None
    first = eff[0]
    return {
        "id":         defn.get("id"),
        "name":       defn.get("name"),
        "type":       defn.get("type"),
        "amount":     sum(e["amount"] for e in eff),
        "recurring":  False,                 # amount is literal — see module note
        "repeat":     None,
        "due":        first.get("due"),
        "added":      first["occ_date"].strftime("%m-%d"),
        "paid":       all(e["paid"] for e in eff),
        "priority":   first.get("priority", 0) or 0,
        "note":       defn.get("note", ""),
        "tags":       list(defn.get("tags", [])),
        "expanded":   False,
        "expandable": False,
        "children":   [],
        # routing + recurrence display metadata (ignored by amount maths)
        "_def_id":      defn.get("id"),
        "_occ":         first["occ_date"].isoformat(),
        "_occ_count":   len(eff),
        "_recur":       defn.get("recurrence") is not None,
        "_recur_repeat": defn.get("recurrence"),
    }


def _view_node(defn: dict, rstart: date, rend: date) -> dict | None:
    kids = defn.get("children") or []
    if kids:
        vk = [v for v in (_view_node(c, rstart, rend) for c in kids) if v]
        if not vk:
            return None
        return {
            "id":         defn.get("id"),
            "name":       defn.get("name"),
            "type":       defn.get("type"),
            "amount":     0.0,
            "recurring":  False, "repeat": None,
            "due":        None, "added": None, "paid": False, "priority": 0,
            "note":       defn.get("note", ""),
            "tags":       list(defn.get("tags", [])),
            "expanded":   bool(defn.get("expanded")),
            "expandable": True,
            "children":   vk,
            "_def_id":      defn.get("id"),
            "_occ":         None,
            "_recur":       False,
            "_recur_repeat": None,
        }
    return _view_leaf(defn, rstart, rend)


def view_nodes(items: list, rstart: date, rend: date) -> tuple[list, list]:
    """(income_nodes, expense_nodes) display trees for everything in the range."""
    inc, exp = [], []
    for defn in items:
        v = _view_node(defn, rstart, rend)
        if v is None:
            continue
        (inc if defn.get("type") == "income" else exp).append(v)
    return inc, exp


def budget_vs_actual(items: list, year: int, month: int) -> dict:
    """Per top-level expense category: ideal (budget) vs actual spend for a month.
    Returns {rows:[{id,name,ideal,actual,tags}], ideal, actual}."""
    last = _cal.monthrange(year, month)[1]
    rs, re = date(year, month, 1), date(year, month, last)
    rows, tot_ideal, tot_actual = [], 0.0, 0.0
    for defn in items:
        if defn.get("type") != "expense":
            continue
        actual = totals_in_range([defn], rs, re)["expenses"]
        ideal  = float(defn.get("ideal", 0.0) or 0.0)
        rows.append({"id": defn.get("id"), "name": defn.get("name"),
                     "ideal": ideal, "actual": actual,
                     "tags": list(defn.get("tags", []))})
        tot_ideal += ideal
        tot_actual += actual
    return {"rows": rows, "ideal": tot_ideal, "actual": tot_actual}


def _norm_merchant(desc: str) -> str:
    """Reduce a bank description to a stable merchant key (drop card refs/dates)."""
    d = _re.sub(r"[^A-Z0-9 ]", " ", (desc or "").upper())
    # drop reference-like tokens (anything with a digit) and single-char noise
    tokens = [t for t in d.split() if len(t) > 1 and not any(c.isdigit() for c in t)]
    return " ".join(tokens[:3])               # first few words identify the merchant


def detect_subscriptions(transactions: list, min_count: int = 2) -> list[dict]:
    """Automatic classification + grouping: cluster transactions by merchant and
    surface the recurring ones as income/outgoing suggestions.
    Returns [{merchant, count, avg_amount, direction, category}]."""
    groups: dict = {}
    for t in transactions:
        key = _norm_merchant(t.get("description", ""))
        if key:
            groups.setdefault(key, []).append(t)
    out = []
    for key, ts in groups.items():
        if len(ts) < min_count:
            continue
        avg = sum(float(x.get("amount", 0.0)) for x in ts) / len(ts)
        out.append({
            "merchant":   key.title(),
            "count":      len(ts),
            "avg_amount": round(abs(avg), 2),
            "direction":  "income" if avg > 0 else "outgoing",
            "category":   ts[-1].get("category"),
        })
    out.sort(key=lambda r: (-r["count"], r["merchant"]))
    return out


def actual_by_category(transactions: list, year: int, month: int) -> dict:
    """Sum of *spend* (money out) per category from imported transactions in
    the month.  Uncategorised spend is bucketed under 'Uncategorised'."""
    res: dict = {}
    for t in transactions:
        d = _parse_iso(t.get("date"))
        if not d or d.year != year or d.month != month:
            continue
        amt = float(t.get("amount", 0.0))
        if amt >= 0:                          # credit / income — not expense spend
            continue
        cat = t.get("category") or "Uncategorised"
        res[cat] = res.get(cat, 0.0) + (-amt)
    return res


def month_has_transactions(transactions: list, year: int, month: int) -> bool:
    for t in transactions:
        d = _parse_iso(t.get("date"))
        if d and d.year == year and d.month == month:
            return True
    return False


def budget_report(items: list, transactions: list, year: int, month: int) -> dict:
    """Per-category ideal vs actual, where actual comes from imported bank
    transactions when any exist for the month, otherwise the planned amount.
    Spend that matches no category is surfaced as its own (non-budgeted) row."""
    last = _cal.monthrange(year, month)[1]
    rs, re = date(year, month, 1), date(year, month, last)
    spend = actual_by_category(transactions, year, month)
    has_txn = month_has_transactions(transactions, year, month)

    rows, tot_ideal, tot_actual, matched = [], 0.0, 0.0, set()
    for defn in items:
        if defn.get("type") != "expense":
            continue
        name    = defn.get("name")
        ideal   = float(defn.get("ideal", 0.0) or 0.0)
        planned = totals_in_range([defn], rs, re)["expenses"]
        imported = spend.get(name, 0.0)
        matched.add(name)
        actual = imported if has_txn else planned
        rows.append({"id": defn.get("id"), "name": name, "ideal": ideal,
                     "actual": actual, "planned": planned, "imported": imported,
                     "tags": list(defn.get("tags", [])),
                     "source": "bank" if has_txn else "planned", "editable": True})
        tot_ideal  += ideal
        tot_actual += actual

    for cat, amt in sorted(spend.items()):
        if cat in matched:
            continue
        rows.append({"id": None, "name": cat, "ideal": 0.0, "actual": amt,
                     "planned": 0.0, "imported": amt, "tags": [],
                     "source": "bank", "editable": False})
        tot_actual += amt

    return {"rows": rows, "ideal": tot_ideal, "actual": tot_actual, "has_txn": has_txn}


def leaf_breakdown(doc: dict, key: str = "income") -> list[tuple[str, float]]:
    """(name, amount) for every leaf in a (synth) doc's income/expense tree."""
    out: list[tuple[str, float]] = []
    def scan(ns):
        for n in ns:
            if n.get("children"):
                scan(n["children"])
            else:
                out.append((n.get("name"), float(n.get("amount", 0.0))))
    scan(doc.get(key, []))
    return out
