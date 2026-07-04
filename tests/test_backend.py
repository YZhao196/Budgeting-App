"""Unit tests for backend.py calculation helpers."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, timedelta
import backend as B
import datamanagement as dm


# --------------------------------------------------------------------------- #
#  Helpers / fixtures
# --------------------------------------------------------------------------- #
def leaf(name, amount, repeat=None, paid=False, due=None):
    return dm.cat(name, amount, repeat=repeat, paid=paid, due=due)


def parent(name, children):
    return dm.cat(name, 0, expandable=True, children=children)


def month_doc(income_nodes, expense_nodes, target=600.0):
    return {
        "month": "2026-05",
        "income": income_nodes,
        "expenses": expense_nodes,
        "target_pnl": target,
        "weekly_budget": 200.0,
        "weeks": 4,
        "currency": "$",
    }


class MockManager:
    def __init__(self, months):
        self._months = months  # {(y, m): doc}

    def list_months(self):
        return sorted(self._months)

    def has_month(self, y, m):
        return (y, m) in self._months

    def load_month(self, y, m):
        return self._months[(y, m)]


# --------------------------------------------------------------------------- #
#  fires_in
# --------------------------------------------------------------------------- #
def test_fires_in_no_repeat():
    assert B.fires_in(None, 2026, 5) is True


# --------------------------------------------------------------------------- #
#  Shared subscriptions — member_shares / who_owes
# --------------------------------------------------------------------------- #
MONTHLY = {"type": "interval", "every": 1, "unit": "month"}


def test_member_shares_even_owner_pays():
    # $27 Spotify Family, 2 friends + owner = 3 heads -> $9 each.
    defn = dm.item("Spotify", 27.0, type="expense", start="2026-06-01",
                   recurrence=MONTHLY,
                   shared={"split": "even", "owner_pays": True,
                           "members": [{"name": "Sam"}, {"name": "Alex"}]})
    rows = B.member_shares(defn, date(2026, 6, 1))
    assert [(r["name"], round(r["share"], 2)) for r in rows] == \
        [("Sam", 9.0), ("Alex", 9.0)]
    assert all(r["paid"] is False for r in rows)


def test_member_shares_even_owner_excluded():
    # owner not paying -> split across the 2 members only -> $13.50 each.
    defn = dm.item("Spotify", 27.0, type="expense", start="2026-06-01",
                   recurrence=MONTHLY,
                   shared={"split": "even", "owner_pays": False,
                           "members": [{"name": "Sam"}, {"name": "Alex"}]})
    rows = B.member_shares(defn, date(2026, 6, 1))
    assert round(rows[0]["share"], 2) == 13.5


def test_member_shares_custom_and_paid_override():
    defn = dm.item("Netflix", 25.0, type="expense", start="2026-06-01",
                   recurrence=MONTHLY,
                   shared={"split": "custom",
                           "members": [{"name": "Sam", "share": 10.0},
                                       {"name": "Alex", "share": 15.0}]},
                   overrides={"2026-06-01": {"member_paid": {"Sam": True}}})
    rows = {r["name"]: r for r in B.member_shares(defn, date(2026, 6, 1))}
    assert rows["Sam"]["share"] == 10.0 and rows["Sam"]["paid"] is True
    assert rows["Alex"]["share"] == 15.0 and rows["Alex"]["paid"] is False


def test_member_shares_skipped_occurrence():
    defn = dm.item("Spotify", 27.0, type="expense", start="2026-06-01",
                   recurrence=MONTHLY,
                   shared={"split": "even", "members": [{"name": "Sam"}]},
                   overrides={"2026-06-01": {"skipped": True}})
    assert B.member_shares(defn, date(2026, 6, 1)) == []


def test_member_shares_ignores_unshared():
    defn = dm.item("Rent", 2000.0, type="expense", start="2026-06-01")
    assert B.member_shares(defn, date(2026, 6, 1)) == []


def test_who_owes_aggregates_across_plans_as_tiers():
    spotify = dm.item("Spotify", 18.0, type="expense", start="2026-06-01",
                      recurrence=MONTHLY,
                      shared={"split": "even", "members": [{"name": "Sam"},
                                                           {"name": "Alex"},
                                                           {"name": "Jo"}]})
    netflix = dm.item("Netflix", 20.0, type="expense", start="2026-06-01",
                      recurrence=MONTHLY,
                      shared={"split": "even", "members": [{"name": "Sam"},
                                                           {"name": "Alex"}]},
                      overrides={"2026-06-01": {"member_paid": {"Sam": True}}})
    rows = {r["member"]: r
            for r in B.who_owes([spotify, netflix],
                                date(2026, 6, 1), date(2026, 6, 30))}
    # Sam is in both plans (the "comprehensive tier"); paid Netflix, owes Spotify.
    assert rows["Sam"]["plans"] == ["Netflix", "Spotify"]
    assert round(rows["Sam"]["total"], 2) == 16.0   # 6 spotify + 10 netflix
    assert round(rows["Sam"]["paid"], 2) == 10.0
    assert round(rows["Sam"]["owes"], 2) == 6.0
    # Jo is only on Spotify.
    assert rows["Jo"]["plans"] == ["Spotify"]
    assert round(rows["Jo"]["owes"], 2) == 6.0


def test_fires_in_days_type():
    assert B.fires_in({"type": "days", "days": [1, 15]}, 2026, 5) is True


def test_fires_in_interval_daily():
    assert B.fires_in({"type": "interval", "every": 1, "unit": "day"}, 2026, 5) is True


def test_fires_in_interval_weekly():
    assert B.fires_in({"type": "interval", "every": 1, "unit": "week"}, 2026, 5) is True


def test_fires_in_monthly_every1():
    r = {"type": "interval", "every": 1, "unit": "month", "anchor": "2026-01"}
    assert B.fires_in(r, 2026, 1) is True
    assert B.fires_in(r, 2026, 6) is True


def test_fires_in_monthly_every2():
    r = {"type": "interval", "every": 2, "unit": "month", "anchor": "2026-01"}
    assert B.fires_in(r, 2026, 1) is True   # anchor month
    assert B.fires_in(r, 2026, 3) is True   # +2 months
    assert B.fires_in(r, 2026, 5) is True   # +4 months
    assert B.fires_in(r, 2026, 2) is False  # +1 month — skipped
    assert B.fires_in(r, 2026, 4) is False  # +3 months — skipped


def test_fires_in_monthly_before_anchor():
    r = {"type": "interval", "every": 1, "unit": "month", "anchor": "2026-06"}
    assert B.fires_in(r, 2026, 5) is False  # before anchor


def test_fires_in_yearly():
    r = {"type": "interval", "every": 1, "unit": "year", "anchor": "2026-03"}
    assert B.fires_in(r, 2026, 3) is True
    assert B.fires_in(r, 2027, 3) is True
    assert B.fires_in(r, 2026, 4) is False  # wrong month


def test_fires_in_unknown_type_returns_false():
    assert B.fires_in({"type": "bogus"}, 2026, 5) is False


# --------------------------------------------------------------------------- #
#  node_amount / active_amount
# --------------------------------------------------------------------------- #
def test_node_amount_leaf():
    n = leaf("Rent", 1000)
    assert B.node_amount(n) == 1000.0


def test_node_amount_parent_sums_children():
    p = parent("Housing", [leaf("Rent", 800), leaf("Rates", 200)])
    assert B.node_amount(p) == 1000.0


def test_active_amount_leaf_no_repeat():
    n = leaf("Bonus", 500)
    assert B.active_amount(n, 2026, 5) == 500.0


def test_active_amount_leaf_repeat_fires():
    n = leaf("Salary", 3000, repeat={"type": "interval", "every": 1, "unit": "month"})
    assert B.active_amount(n, 2026, 5) == 3000.0


def test_active_amount_leaf_repeat_does_not_fire():
    r = {"type": "interval", "every": 2, "unit": "month", "anchor": "2026-01"}
    n = leaf("Rent", 1000, repeat=r)
    assert B.active_amount(n, 2026, 2) == 0.0  # doesn't fire in Feb


def test_active_amount_parent_sums_active_children():
    r_fires = {"type": "interval", "every": 1, "unit": "month"}
    r_skip = {"type": "interval", "every": 2, "unit": "month", "anchor": "2026-01"}
    p = parent("Mixed", [
        leaf("Monthly", 500, repeat=r_fires),
        leaf("Bimonthly", 200, repeat=r_skip),
    ])
    # in Feb: bimonthly skips → only 500
    assert B.active_amount(p, 2026, 2) == 500.0
    # in Mar: bimonthly fires → 500 + 200
    assert B.active_amount(p, 2026, 3) == 700.0


# --------------------------------------------------------------------------- #
#  income_total / expense_total / pnl / savings_rate
# --------------------------------------------------------------------------- #
def test_income_total():
    doc = month_doc([leaf("Salary", 5000)], [])
    assert B.income_total(doc) == 5000.0


def test_expense_total():
    doc = month_doc([], [leaf("Rent", 1200)])
    assert B.expense_total(doc) == 1200.0


def test_pnl():
    doc = month_doc([leaf("Salary", 5000)], [leaf("Rent", 2000)])
    assert B.pnl(doc) == 3000.0


def test_pnl_negative():
    doc = month_doc([leaf("Salary", 1000)], [leaf("Bills", 1500)])
    assert B.pnl(doc) == -500.0


def test_savings_rate():
    doc = month_doc([leaf("Salary", 4000)], [leaf("Expenses", 1000)])
    assert abs(B.savings_rate(doc) - 0.75) < 1e-9


def test_savings_rate_zero_income():
    doc = month_doc([], [leaf("Expenses", 500)])
    assert B.savings_rate(doc) == 0.0


# --------------------------------------------------------------------------- #
#  priority
# --------------------------------------------------------------------------- #
def test_priority_paid():
    n = leaf("Bill", 100, paid=True, due="2026-05-01")
    assert B.priority(n, date(2026, 5, 15)) == B.PRIORITY_OK


def test_priority_no_due():
    n = leaf("Bill", 100)
    assert B.priority(n, date(2026, 5, 15)) == B.PRIORITY_NONE


def test_priority_overdue():
    n = leaf("Bill", 100, due="2026-05-01")
    assert B.priority(n, date(2026, 5, 20)) == B.PRIORITY_OVERDUE


def test_priority_soon():
    n = leaf("Bill", 100, due="2026-05-20")
    assert B.priority(n, date(2026, 5, 10)) == B.PRIORITY_SOON


def test_priority_ok():
    n = leaf("Bill", 100, due="2026-06-30")
    assert B.priority(n, date(2026, 5, 1)) == B.PRIORITY_OK


# --------------------------------------------------------------------------- #
#  weekly_budgets
# --------------------------------------------------------------------------- #
def test_weekly_budgets_structure():
    doc = month_doc([], [], target=600)
    doc["weekly_budget"] = 250.0
    doc["weeks"] = 4
    wb = B.weekly_budgets(doc)
    assert wb["weekly"] == 250.0
    assert wb["weeks"] == 4
    assert wb["total_budget"] == 1000.0
    assert len(wb["rows"]) == 4
    # each row is a dict with the right keys
    r = wb["rows"][0]
    assert r["week"] == 1
    assert r["budget"] == 250.0
    assert r["bills"] == []
    assert r["bills_total"] == 0.0


def test_weekly_budgets_bills_assigned_to_correct_week():
    # Week assignment uses added day-of-month (not due date)
    from datamanagement import cat
    expenses = [
        cat("Rent",     2000, type="expense", added="06-01"),   # day  1 → week 1
        cat("Electric",  150, type="expense", added="06-20"),   # day 20 → week 3
        cat("Water",      50, type="expense", added="06-03"),   # day  3 → week 1
    ]
    doc = {
        "month": "2026-06",
        "income": [],
        "expenses": expenses,
        "target_pnl": 0,
        "weekly_budget": 200.0,
        "weeks": 4,
        "currency": "$",
    }
    wb = B.weekly_budgets(doc)
    assert len(wb["rows"]) == 4
    # week 1: Rent + Water
    assert any(n == "Rent"  for n, _ in wb["rows"][0]["bills"])
    assert any(n == "Water" for n, _ in wb["rows"][0]["bills"])
    assert wb["rows"][0]["bills_total"] == 2050.0
    # week 2: nothing
    assert wb["rows"][1]["bills"] == []
    # week 3 (Jun 15-21): Electric
    assert any(n == "Electric" for n, _ in wb["rows"][2]["bills"])
    assert wb["rows"][2]["bills_total"] == 150.0


def test_period_summary_weekly_with_week_of_month():
    # Week assignment uses added day-of-month; amounts are NOT divided by n_weeks
    from datamanagement import cat
    expenses = [
        cat("Rent",      2000, type="expense", added="06-01"),   # day  1 → week 1
        cat("Wifi",       100, type="expense", added="06-15"),   # day 15 → week 3
        cat("Groceries",  400, type="expense", added="06-05"),   # day  5 → week 1
    ]
    income = [cat("Salary", 4000, recurring=True, added="06-01")]  # day 1 → week 1
    doc = {
        "month": "2026-06",
        "income": income,
        "expenses": expenses,
        "target_pnl": 0,
        "weekly_budget": 0,
        "weeks": 4,
        "currency": "$",
    }
    docs = {(2026, 6): doc}
    mgr = MockManager(docs)

    # Week 1 (Jun 1-7): Rent (2000) + Groceries (400); Salary (4000) — no division
    s1 = B.period_summary(mgr, 2026, 6, "Weekly", week_of_month=1)
    assert s1["expenses"] == pytest.approx(2400.0)
    assert s1["income"]   == pytest.approx(4000.0)

    # Week 3 (Jun 15-21): only Wifi (100); no income items added in wk3
    s3 = B.period_summary(mgr, 2026, 6, "Weekly", week_of_month=3)
    assert s3["expenses"] == pytest.approx(100.0)
    assert s3["income"]   == pytest.approx(0.0)

    # Week 2: nothing
    s2 = B.period_summary(mgr, 2026, 6, "Weekly", week_of_month=2)
    assert s2["expenses"] == pytest.approx(0.0)
    assert s2["income"]   == pytest.approx(0.0)

    # No week_of_month → avg fallback still divides full monthly totals
    s_avg = B.period_summary(mgr, 2026, 6, "Weekly")
    assert s_avg["expenses"] == pytest.approx(2500.0 / 4)  # (2000+100+400)/4


def test_month_week_ranges_covers_whole_month():
    import calendar
    ranges = B.month_week_ranges(2026, 6, 4)
    assert ranges[0][1].day == 1                           # starts on the 1st
    assert ranges[-1][2].day == 30                         # ends on the 30th
    # all days covered
    covered = set()
    for _, start, end in ranges:
        d = start
        while d <= end:
            covered.add(d.day)
            d = d + timedelta(days=1)
    assert covered == set(range(1, 31))


def test_month_week_ranges_five_week_month():
    # March 2026 has 31 days; with weeks=5 all days should be covered
    ranges = B.month_week_ranges(2026, 3, 5)
    assert len(ranges) == 5
    assert ranges[-1][2].day == 31


# --------------------------------------------------------------------------- #
#  history
# --------------------------------------------------------------------------- #
def test_history_basic():
    docs = {}
    for m in range(1, 6):
        docs[(2026, m)] = month_doc([leaf("Salary", 5000)], [leaf("Bills", 3000 + m * 100)])
    mgr = MockManager(docs)
    h = B.history(mgr, 2026, 5, 5)
    assert len(h) == 5
    labels = [lab for lab, _, _ in h]
    assert labels == ["Jan", "Feb", "Mar", "Apr", "May"]
    # May: 5000 - 3500 = 1500
    assert h[-1][1] == pytest.approx(1500.0)
    assert h[-1][2] is True   # is_current


def test_history_missing_month_is_zero():
    docs = {(2026, 5): month_doc([leaf("Salary", 5000)], [leaf("Bills", 3000)])}
    mgr = MockManager(docs)
    h = B.history(mgr, 2026, 5, 3)
    # Jan and Apr have no data → 0
    assert h[0][1] == 0.0
    assert h[1][1] == 0.0
    assert h[2][1] == 2000.0


# --------------------------------------------------------------------------- #
#  period_summary
# --------------------------------------------------------------------------- #
def test_period_summary_monthly():
    docs = {(2026, 5): month_doc([leaf("Salary", 5000)], [leaf("Rent", 2000)])}
    mgr = MockManager(docs)
    s = B.period_summary(mgr, 2026, 5, "Monthly")
    assert s["income"] == 5000.0
    assert s["expenses"] == 2000.0
    assert s["pnl"] == 3000.0


def test_period_summary_weekly_divides_by_weeks():
    doc = month_doc([leaf("Salary", 4000)], [leaf("Bills", 2000)])
    doc["weeks"] = 4
    docs = {(2026, 5): doc}
    mgr = MockManager(docs)
    s = B.period_summary(mgr, 2026, 5, "Weekly")
    assert s["income"] == 1000.0
    assert s["expenses"] == 500.0


def test_period_summary_ytd():
    docs = {}
    for m in range(1, 6):
        docs[(2026, m)] = month_doc([leaf("Salary", 1000)], [leaf("Bills", 600)])
    mgr = MockManager(docs)
    s = B.period_summary(mgr, 2026, 3, "YTD")
    assert s["income"] == 3000.0   # Jan+Feb+Mar
    assert s["expenses"] == 1800.0
    assert s["pnl"] == 1200.0


def test_period_summary_yearly():
    docs = {}
    for m in range(1, 6):
        docs[(2026, m)] = month_doc([leaf("Salary", 1000)], [leaf("Bills", 600)])
    docs[(2025, 12)] = month_doc([leaf("Bonus", 5000)], [])  # different year
    mgr = MockManager(docs)
    s = B.period_summary(mgr, 2026, 3, "Yearly")
    assert s["income"] == 5000.0   # all 5 months of 2026 only
    assert s["pnl"] == 2000.0


# --------------------------------------------------------------------------- #
#  Flat-store model (3a): occurrence engine
# --------------------------------------------------------------------------- #
def _def(**kw):
    from datamanagement import item
    return item(**kw)


def test_occ_one_off_in_range():
    d = _def(name="X", amount=10, start="2026-05-10")
    assert B.occurrence_dates(d, date(2026, 5, 1), date(2026, 5, 31)) == [date(2026, 5, 10)]


def test_occ_one_off_outside_range():
    d = _def(name="X", amount=10, start="2026-05-10")
    assert B.occurrence_dates(d, date(2026, 6, 1), date(2026, 6, 30)) == []


def test_occ_monthly():
    d = _def(name="X", amount=10, start="2026-01-01",
             recurrence={"type": "interval", "every": 1, "unit": "month"})
    got = B.occurrence_dates(d, date(2026, 1, 1), date(2026, 3, 31))
    assert got == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_occ_every_2_months():
    d = _def(name="X", amount=10, start="2026-01-15",
             recurrence={"type": "interval", "every": 2, "unit": "month"})
    got = B.occurrence_dates(d, date(2026, 1, 1), date(2026, 6, 30))
    assert got == [date(2026, 1, 15), date(2026, 3, 15), date(2026, 5, 15)]


def test_occ_weekly_across_month_boundary():
    d = _def(name="X", amount=10, start="2026-03-30",
             recurrence={"type": "interval", "every": 1, "unit": "week"})
    got = B.occurrence_dates(d, date(2026, 3, 30), date(2026, 4, 13))
    assert got == [date(2026, 3, 30), date(2026, 4, 6), date(2026, 4, 13)]


def test_occ_daily_window():
    d = _def(name="X", amount=1, start="2026-05-01",
             recurrence={"type": "interval", "every": 1, "unit": "day"})
    got = B.occurrence_dates(d, date(2026, 5, 5), date(2026, 5, 8))
    assert got == [date(2026, 5, 5), date(2026, 5, 6), date(2026, 5, 7), date(2026, 5, 8)]


def test_occ_yearly():
    d = _def(name="X", amount=10, start="2026-03-03",
             recurrence={"type": "interval", "every": 1, "unit": "year"})
    got = B.occurrence_dates(d, date(2026, 1, 1), date(2028, 12, 31))
    assert got == [date(2026, 3, 3), date(2027, 3, 3), date(2028, 3, 3)]


def test_occ_days_of_month():
    d = _def(name="X", amount=10, start="2026-05-01",
             recurrence={"type": "days", "days": [1, 15]})
    got = B.occurrence_dates(d, date(2026, 5, 1), date(2026, 6, 30))
    assert got == [date(2026, 5, 1), date(2026, 5, 15),
                   date(2026, 6, 1), date(2026, 6, 15)]


def test_occ_respects_end():
    d = _def(name="X", amount=10, start="2026-01-01", end="2026-02-28",
             recurrence={"type": "interval", "every": 1, "unit": "month"})
    got = B.occurrence_dates(d, date(2026, 1, 1), date(2026, 12, 31))
    assert got == [date(2026, 1, 1), date(2026, 2, 1)]


def test_instances_override_amount_and_skip():
    d = _def(name="Rent", amount=500, type="expense", start="2026-01-01",
             recurrence={"type": "interval", "every": 1, "unit": "month"},
             overrides={"2026-02-01": {"amount": 600},
                        "2026-03-01": {"skipped": True}})
    insts = B.instances_in_range([d], date(2026, 1, 1), date(2026, 3, 31))
    by_month = {i["occ_date"].month: i["amount"] for i in insts}
    assert by_month == {1: 500.0, 2: 600.0}   # March skipped entirely


def test_totals_in_range_income_minus_expense():
    inc = _def(name="Salary", amount=1000, type="income", start="2026-05-01",
               recurrence={"type": "interval", "every": 1, "unit": "month"})
    exp = _def(name="Rent", amount=400, type="expense", start="2026-05-01",
               recurrence={"type": "interval", "every": 1, "unit": "month"})
    t = B.totals_in_range([inc, exp], date(2026, 5, 1), date(2026, 5, 31))
    assert t["income"] == 1000.0 and t["expenses"] == 400.0 and t["pnl"] == 600.0


# --------------------------------------------------------------------------- #
#  Time lenses
# --------------------------------------------------------------------------- #
def test_lens_month_range():
    s, e, _ = B.range_for_lens("month", date(2026, 5, 17))
    assert s == date(2026, 5, 1) and e == date(2026, 5, 31)


def test_lens_iso_week_spans_month_boundary():
    # Wed Apr 1 2026 → ISO week Mon Mar 30 .. Sun Apr 5
    s, e, _ = B.range_for_lens("iso_week", date(2026, 4, 1))
    assert s == date(2026, 3, 30) and e == date(2026, 4, 5)


def test_lens_monday_in_month_clamps_to_first():
    # Apr 1 2026 is a Wednesday; week 1 clamps start to the 1st
    s, e, _ = B.range_for_lens("monday_in_month", date(2026, 4, 1))
    assert s == date(2026, 4, 1) and e == date(2026, 4, 5)


def test_step_lens_iso_week():
    nxt = B.step_lens("iso_week", date(2026, 4, 1), 1)
    assert nxt == date(2026, 4, 6)       # next Monday
    prv = B.step_lens("iso_week", date(2026, 4, 1), -1)
    assert prv == date(2026, 3, 23)


def test_step_lens_month():
    assert B.step_lens("month", date(2026, 5, 17), 1) == date(2026, 6, 1)
    assert B.step_lens("month", date(2026, 1, 10), -1) == date(2025, 12, 1)


# --------------------------------------------------------------------------- #
#  Migration fidelity: per-month totals survive the flat-store conversion
# --------------------------------------------------------------------------- #
def test_migration_preserves_month_totals():
    from datamanagement import cat, _migrate_months_to_items
    jan = month_doc([cat("Salary", 1000, recurring=True)],
                    [cat("Rent", 500, type="expense", recurring=True)])
    jan["month"] = "2026-01"
    feb = month_doc([cat("Salary", 1000, recurring=True)],
                    [cat("Rent", 600, type="expense", recurring=True)])
    feb["month"] = "2026-02"
    mgr = MockManager({(2026, 1): jan, (2026, 2): feb})
    items = _migrate_months_to_items(mgr)["items"]

    jt = B.totals_in_range(items, date(2026, 1, 1), date(2026, 1, 31))
    ft = B.totals_in_range(items, date(2026, 2, 1), date(2026, 2, 28))
    assert jt["income"] == 1000.0 and jt["expenses"] == 500.0
    assert ft["income"] == 1000.0 and ft["expenses"] == 600.0
    # recurring items continue forward using the latest month's base amount
    mar = B.totals_in_range(items, date(2026, 3, 1), date(2026, 3, 31))
    assert mar["income"] == 1000.0 and mar["expenses"] == 600.0


def test_migration_nested_children_preserved():
    from datamanagement import cat, _migrate_months_to_items
    inc = [cat("Resale", 0, expanded=True, children=[
                cat("eBay", 250, recurring=True),
                cat("Marketplace", 150, recurring=True)])]
    doc = month_doc(inc, [])
    doc["month"] = "2026-05"
    mgr = MockManager({(2026, 5): doc})
    items = _migrate_months_to_items(mgr)["items"]
    assert items[0]["name"] == "Resale"
    assert [c["name"] for c in items[0]["children"]] == ["eBay", "Marketplace"]
    t = B.totals_in_range(items, date(2026, 5, 1), date(2026, 5, 31))
    assert t["income"] == 400.0


# --------------------------------------------------------------------------- #
#  Edit scopes (instance / future / all) — store ops the scope dialog drives
# --------------------------------------------------------------------------- #
def _store_with(items):
    s = dm.ItemStore()
    s._data = {"items": items, "settings": {"currency": "$", "time_lens": "iso_week"},
               "period_settings": {}}
    s.save = lambda: None        # keep the test off disk
    return s


def _monthly(name, amount, type="expense", start="2026-01-01"):
    from datamanagement import item
    return item(name, amount, type=type, start=start,
                recurrence={"type": "interval", "every": 1, "unit": "month"})


def _exp(items, y, m):
    import calendar
    last = calendar.monthrange(y, m)[1]
    return B.totals_in_range(items, date(y, m, 1), date(y, m, last))["expenses"]


def test_edit_scope_instance():
    d = _monthly("Rent", 500)
    s = _store_with([d])
    s.edit_field(d["id"], "2026-02-01", "amount", 600, scope="instance")
    items = s.items()
    assert _exp(items, 2026, 1) == 500
    assert _exp(items, 2026, 2) == 600   # only February
    assert _exp(items, 2026, 3) == 500


def test_edit_scope_all():
    d = _monthly("Rent", 500)
    s = _store_with([d])
    s.edit_field(d["id"], "2026-02-01", "amount", 600, scope="all")
    items = s.items()
    assert _exp(items, 2026, 1) == 600
    assert _exp(items, 2026, 2) == 600
    assert _exp(items, 2026, 3) == 600   # whole series


def test_edit_scope_future():
    d = _monthly("Rent", 500)
    s = _store_with([d])
    s.edit_field(d["id"], "2026-03-01", "amount", 600, scope="future")
    items = s.items()
    assert _exp(items, 2026, 1) == 500   # past untouched
    assert _exp(items, 2026, 2) == 500
    assert _exp(items, 2026, 3) == 600   # this + future
    assert _exp(items, 2026, 4) == 600


def test_delete_occurrence_scopes():
    # single → skip that month only
    d = _monthly("Rent", 500)
    s = _store_with([d])
    s.delete_occurrence(d["id"], "2026-02-01", scope="single")
    items = s.items()
    assert _exp(items, 2026, 1) == 500
    assert _exp(items, 2026, 2) == 0     # skipped
    assert _exp(items, 2026, 3) == 500

    # future → ends the series before this occurrence
    d2 = _monthly("Wifi", 100)
    s2 = _store_with([d2])
    s2.delete_occurrence(d2["id"], "2026-03-01", scope="future")
    i2 = s2.items()
    assert _exp(i2, 2026, 2) == 100
    assert _exp(i2, 2026, 3) == 0
    assert _exp(i2, 2026, 4) == 0

    # all → removes the definition entirely
    d3 = _monthly("Gym", 40)
    s3 = _store_with([d3])
    s3.delete_occurrence(d3["id"], "2026-02-01", scope="all")
    assert s3.items() == []


# --------------------------------------------------------------------------- #
#  Budget (ideal vs actual) + tags
# --------------------------------------------------------------------------- #
def test_budget_vs_actual():
    from datamanagement import item
    rent = item("Rent", 500, type="expense", start="2026-01-01",
                recurrence={"type": "interval", "every": 1, "unit": "month"}, ideal=600)
    gym  = item("Gym", 40, type="expense", start="2026-01-01",
                recurrence={"type": "interval", "every": 1, "unit": "month"})
    sal  = item("Salary", 1000, type="income", start="2026-01-01",
                recurrence={"type": "interval", "every": 1, "unit": "month"})
    data = B.budget_vs_actual([sal, rent, gym], 2026, 3)
    rows = {r["name"]: r for r in data["rows"]}
    assert "Salary" not in rows                      # income excluded
    assert rows["Rent"]["ideal"] == 600 and rows["Rent"]["actual"] == 500
    assert rows["Gym"]["ideal"] == 0 and rows["Gym"]["actual"] == 40
    assert data["ideal"] == 600 and data["actual"] == 540


def test_set_ideal_and_tags():
    d = _monthly("Rent", 500)
    s = _store_with([d])
    s.set_ideal(d["id"], 600)
    assert s._find_def(d["id"])["ideal"] == 600
    # tags are de-duplicated (case-insensitive) and trimmed
    s.set_tags(d["id"], ["Fixed", "  fixed ", "Home", ""])
    assert s._find_def(d["id"])["tags"] == ["Fixed", "Home"]
    assert s.all_tags() == ["Fixed", "Home"]


# need pytest.approx for float comparisons
try:
    import pytest
except ImportError:
    class _pytest:
        @staticmethod
        def approx(v, rel=None, abs=None): return v
    pytest = _pytest()


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
