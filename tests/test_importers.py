"""Tests for the bank-statement importers, categorisation and budget report."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date
import importers as IMP
import backend as B
import datamanagement as dm


def _store_with(items, transactions=None, rules=None):
    s = dm.ItemStore()
    s._data = {"items": items, "settings": {"currency": "$", "time_lens": "iso_week"},
               "period_settings": {}, "transactions": transactions or [],
               "rules": rules or []}
    s.save = lambda: None
    return s


def _monthly_exp(name, amount, ideal=0.0):
    return dm.item(name, amount, type="expense", start="2026-01-01",
                   recurrence={"type": "interval", "every": 1, "unit": "month"},
                   ideal=ideal)


# --------------------------------------------------------------------------- #
#  CSV parsing
# --------------------------------------------------------------------------- #
def test_csv_anz_classic_no_header():
    text = ("01/06/2026,-100.00,WOOLWORTHS\n"
            "03/06/2026,2500.00,SALARY ANZ\n"
            "05/06/2026,-50.50,WIFI PROVIDER\n")
    txns = IMP.parse_csv(text)
    assert len(txns) == 3
    assert txns[0] == {"date": "2026-06-01", "amount": -100.0, "description": "WOOLWORTHS"}
    assert txns[1]["amount"] == 2500.0
    assert txns[2]["amount"] == -50.5


def test_csv_with_header_iso_dates():
    text = ("Date,Amount,Description\n"
            "2026-06-01,-100.00,Woolworths\n"
            "2026-06-02,-25.00,Cafe\n")
    txns = IMP.parse_csv(text)
    assert [t["date"] for t in txns] == ["2026-06-01", "2026-06-02"]
    assert txns[0]["description"] == "Woolworths"


def test_csv_separate_debit_credit_columns():
    text = ("Date,Debit,Credit,Description\n"
            "01/06/2026,100.00,,Woolworths\n"
            "03/06/2026,,2500.00,Salary\n")
    txns = IMP.parse_csv(text)
    amounts = {t["description"]: t["amount"] for t in txns}
    assert amounts["Woolworths"] == -100.0
    assert amounts["Salary"] == 2500.0


def test_ofx_parsing():
    text = (
        "<OFX><BANKMSGSRSV1><STMTTRNRS><BANKTRANLIST>"
        "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260601<TRNAMT>-100.00<NAME>WOOLWORTHS</STMTTRN>"
        "<STMTTRN><DTPOSTED>20260603120000<TRNAMT>2500.00<NAME>SALARY</STMTTRN>"
        "</BANKTRANLIST></STMTTRNRS></BANKMSGSRSV1></OFX>")
    txns = IMP.parse_ofx(text)
    assert len(txns) == 2
    assert txns[0] == {"date": "2026-06-01", "amount": -100.0, "description": "WOOLWORTHS"}
    assert txns[1]["date"] == "2026-06-03" and txns[1]["amount"] == 2500.0


# --------------------------------------------------------------------------- #
#  Import + categorisation
# --------------------------------------------------------------------------- #
def test_import_categorises_by_item_name():
    s = _store_with([_monthly_exp("Wifi", 100)])
    raw = [{"date": "2026-06-05", "amount": -50.5, "description": "WIFI PROVIDER PTY"}]
    res = s.import_transactions(raw, account="ANZ")
    assert res["added"] == 1 and res["categorised"] == 1
    assert s.transactions()[0]["category"] == "Wifi"
    assert s.transactions()[0]["account"] == "ANZ"


def test_import_dedups():
    s = _store_with([])
    raw = [{"date": "2026-06-05", "amount": -50.5, "description": "WIFI"}]
    s.import_transactions(raw, account="ANZ")
    res = s.import_transactions(raw, account="ANZ")     # same file again
    assert res["added"] == 0 and res["skipped"] == 1
    assert len(s.transactions()) == 1


def test_rule_overrides_name_match():
    s = _store_with([_monthly_exp("Groceries", 0)])
    s.add_rule("woolworths", "Groceries", ["Essential"])
    s.import_transactions(
        [{"date": "2026-06-01", "amount": -80.0, "description": "WOOLWORTHS METRO"}],
        account="ANZ")
    t = s.transactions()[0]
    assert t["category"] == "Groceries" and t["tags"] == ["Essential"]


# --------------------------------------------------------------------------- #
#  Actuals → budget report
# --------------------------------------------------------------------------- #
def test_actual_by_category_spend_only():
    txns = [
        {"date": "2026-06-01", "amount": -100.0, "category": "Groceries"},
        {"date": "2026-06-08", "amount": -40.0, "category": "Groceries"},
        {"date": "2026-06-03", "amount": 2500.0, "category": None},   # income → ignored
        {"date": "2026-05-30", "amount": -20.0, "category": "Groceries"},  # other month
    ]
    res = B.actual_by_category(txns, 2026, 6)
    assert res == {"Groceries": 140.0}


def test_budget_report_uses_imported_actuals():
    items = [_monthly_exp("Wifi", 100, ideal=60),
             _monthly_exp("Rent", 2000, ideal=2000)]
    txns = [
        {"date": "2026-06-05", "amount": -55.0, "category": "Wifi"},
        {"date": "2026-06-01", "amount": -2000.0, "category": "Rent"},
        {"date": "2026-06-10", "amount": -30.0, "category": None},   # uncategorised
    ]
    rep = B.budget_report(items, txns, 2026, 6)
    rows = {r["name"]: r for r in rep["rows"]}
    assert rep["has_txn"] is True
    assert rows["Wifi"]["actual"] == 55.0 and rows["Wifi"]["ideal"] == 60
    assert rows["Rent"]["actual"] == 2000.0
    # uncategorised spend appears as its own non-editable row
    assert rows["Uncategorised"]["actual"] == 30.0
    assert rows["Uncategorised"]["editable"] is False


def test_budget_report_falls_back_to_planned_without_txns():
    items = [_monthly_exp("Wifi", 100, ideal=60)]
    rep = B.budget_report(items, [], 2026, 6)
    rows = {r["name"]: r for r in rep["rows"]}
    assert rep["has_txn"] is False
    assert rows["Wifi"]["actual"] == 100.0           # planned amount used


def test_detect_subscriptions_groups_recurring_merchants():
    txns = [
        {"date": "2026-04-05", "amount": -11.99, "description": "SPOTIFY P12345"},
        {"date": "2026-05-05", "amount": -11.99, "description": "SPOTIFY P67890"},
        {"date": "2026-06-05", "amount": -11.99, "description": "SPOTIFY P11111"},
        {"date": "2026-05-01", "amount": 2500.0, "description": "ACME CO PAYMENT 99"},
        {"date": "2026-06-01", "amount": 2500.0, "description": "ACME CO PAYMENT 77"},
        {"date": "2026-06-09", "amount": -4.50, "description": "ONE OFF CAFE"},
    ]
    by = {r["merchant"]: r for r in B.detect_subscriptions(txns)}
    assert by["Spotify"]["count"] == 3 and by["Spotify"]["direction"] == "outgoing"
    assert by["Acme Co Payment"]["direction"] == "income"
    assert "One Off Cafe" not in by          # appears once → not recurring


def test_plan_summary_expense_net_cost():
    # Spotify Family $27, even, owner counts as a payer, 2 friends -> $9 heads.
    defn = dm.item("Spotify", 27.0, type="expense", start="2026-06-01",
                   recurrence={"type": "interval", "every": 1, "unit": "month"},
                   shared={"split": "even", "owner_pays": True,
                           "members": [{"name": "Sam"}, {"name": "Alex"}]})
    s = B.plan_summary(defn, date(2026, 6, 1))
    assert s["total"] == 27.0
    assert round(s["member_total"], 2) == 18.0      # the two friends owe $9 each
    assert round(s["your_net"], 2) == 9.0           # your own share — the real cost
    assert s["recovered"] == 0.0 and round(s["outstanding"], 2) == 18.0
    assert s["ready"] is False
    # both friends pay back
    defn["overrides"] = {"2026-06-01": {"member_paid": {"Sam": True, "Alex": True}}}
    s2 = B.plan_summary(defn, date(2026, 6, 1))
    assert round(s2["recovered"], 2) == 18.0 and s2["outstanding"] == 0.0
    assert s2["ready"] is True


def test_plan_summary_income_gated():
    defn = dm.item("Acme batch", 4000.0, type="income", start="2026-06-01",
                   recurrence={"type": "interval", "every": 1, "unit": "month"},
                   shared={"split": "custom",
                           "members": [{"name": "Acme", "share": 2500.0},
                                       {"name": "Globex", "share": 1500.0}]},
                   overrides={"2026-06-01": {"member_paid": {"Acme": True}}})
    s = B.plan_summary(defn, date(2026, 6, 1))
    assert s["total"] == 4000.0 and s["member_total"] == 4000.0
    assert s["recovered"] == 2500.0 and s["outstanding"] == 1500.0
    assert s["ready"] is False                       # Globex hasn't paid → don't ship


def test_subscription_flag():
    e = _monthly_exp("Netflix", 20.0)
    s = _store_with([e, _monthly_exp("Rent", 2000.0)])
    assert s.subscriptions() == []
    s.set_subscription(e["id"], True)
    assert [d["name"] for d in s.subscriptions()] == ["Netflix"]   # rent stays out


_MO = {"type": "interval", "every": 1, "unit": "month"}


def test_people_roster_per_person_breakdown():
    spot = dm.item("Spotify", 18.0, type="expense", start="2026-06-01", recurrence=_MO,
                   shared={"split": "even", "members": [{"name": "Sam"},
                           {"name": "Alex"}, {"name": "Jo"}]})
    net = dm.item("Netflix", 20.0, type="expense", start="2026-06-01", recurrence=_MO,
                  shared={"split": "even", "members": [{"name": "Sam"}, {"name": "Alex"}]},
                  overrides={"2026-06-01": {"member_paid": {"Sam": True}}})
    roster = {p["member"]: p
              for p in B.people_roster([spot, net], date(2026, 6, 1), date(2026, 6, 30))}
    assert round(roster["Sam"]["total"], 2) == 16.0     # $6 Spotify + $10 Netflix
    assert round(roster["Sam"]["paid"], 2) == 10.0      # paid Netflix only
    assert round(roster["Sam"]["owes"], 2) == 6.0
    assert {pl["name"] for pl in roster["Sam"]["plans"]} == {"Spotify", "Netflix"}
    assert round(roster["Jo"]["owes"], 2) == 6.0        # only on Spotify


def test_recurring_payments_sorted_by_next():
    rent = dm.item("Rent", 2000, type="expense", start="2026-01-01", recurrence=_MO)
    sal  = dm.item("Salary", 5000, type="income", start="2026-01-15", recurrence=_MO)
    rows = B.recurring_payments([rent, sal], date(2026, 6, 5))
    # Salary next (Jun 15) comes before Rent next (Jul 1)
    assert [r["name"] for r in rows] == ["Salary", "Rent"]
    assert rows[0]["next"] == "2026-06-15" and rows[1]["next"] == "2026-07-01"


def test_monthly_equiv():
    assert B.monthly_equiv(120, {"type": "interval", "every": 1, "unit": "year"}) == 10.0
    assert B.monthly_equiv(30, {"type": "interval", "every": 1, "unit": "month"}) == 30.0
    assert round(B.monthly_equiv(10, {"type": "interval", "every": 1, "unit": "week"}), 2) == 43.45


def test_search():
    items = [dm.item("Spotify Family", 27, type="expense", start="2026-06-01",
                     recurrence=_MO, shared={"split": "even", "members": [{"name": "Sam"}]}),
             dm.item("Rent", 2000, type="expense", start="2026-06-01", recurrence=_MO,
                     tags=["Fixed"])]
    s = _store_with(items)
    s.add_account("ANZ Plus", "cash", 100)
    s.add_person("Sam")
    assert any(r["kind"] == "Subscription" and r["name"] == "Spotify Family"
               for r in B.search(s, "spot"))
    assert any(r["name"] == "Rent" for r in B.search(s, "fixed"))      # tag match
    assert any(r["kind"] == "Account" for r in B.search(s, "anz"))
    assert any(r["kind"] == "Person" for r in B.search(s, "sam"))
    assert B.search(s, "") == []


def test_net_worth_and_liquid():
    accs = [dm.account("ANZ", "cash", 2500), dm.account("Savings", "savings", 12000),
            dm.account("Shares", "investment", 8000), dm.account("Car", "asset", 15000),
            dm.account("Home loan", "debt", 30000), dm.account("Visa", "credit", 1200)]
    nw = B.net_worth(accs)
    assert nw["assets"] == 37500
    assert nw["liabilities"] == 31200
    assert nw["net"] == 6300
    assert B.liquid_balance(accs) == 14500       # cash + savings only


def test_forecast():
    inc = dm.item("Salary", 5000, type="income", start="2026-01-01", recurrence=_MO)
    exp = dm.item("Bills", 4000, type="expense", start="2026-01-01", recurrence=_MO)
    fc = B.forecast([inc, exp], 1000, date(2026, 6, 24), 3)
    assert [round(r["balance"]) for r in fc] == [2000, 3000, 4000]
    assert fc[0]["pnl"] == 1000


def test_account_store_ops():
    s = _store_with([])
    a = s.add_account("ANZ", "cash", 1000)
    assert [x["name"] for x in s.accounts()] == ["ANZ"]
    s.update_account(a["id"], balance=1500.0, kind="savings")
    got = next(x for x in s.accounts() if x["id"] == a["id"])
    assert got["balance"] == 1500.0 and got["kind"] == "savings"
    s.remove_account(a["id"])
    assert s.accounts() == []


def test_add_person_stores_contact_details():
    s = _store_with([])
    p = s.add_person("Sam", email="sam@x.com", phone="0400", note="housemate")
    assert p["email"] == "sam@x.com" and p["phone"] == "0400"
    assert p["note"] == "housemate" and p["id"]
    # same name again: no duplicate; blank fields get filled, set ones kept
    p2 = s.add_person("sam", email="new@x.com", note="")
    assert len(s.people()) == 1
    assert p2["email"] == "sam@x.com"          # existing value wins


def test_update_person_renames_in_shared_plans():
    sub = dm.item("Spotify", 27, type="expense", start="2026-01-01",
                  recurrence=_MO,
                  shared={"split": "even", "owner_pays": False,
                          "members": [{"name": "Sam"}]})
    s = _store_with([sub])
    p = s.add_person("Sam", email="sam@x.com")
    s.update_person(p["id"], name="Samuel", phone="0400")
    got = s.people()[0]
    assert got["name"] == "Samuel" and got["phone"] == "0400"
    assert got["email"] == "sam@x.com"          # untouched field survives
    assert sub["shared"]["members"][0]["name"] == "Samuel"


def test_upcoming_renewals():
    today = date(2026, 6, 24)
    netflix = dm.item("Netflix", 20, type="expense", start="2026-06-26",
                      recurrence=_MO, subscription=True)
    gym = dm.item("Gym", 50, type="expense", start="2026-06-01",
                  recurrence=_MO, subscription=True)        # next Jul 1 (7d away)
    rent = dm.item("Rent", 2000, type="expense", start="2026-06-01",
                   recurrence=_MO)                          # not a subscription
    res = B.upcoming_renewals([netflix, gym, rent], today, days=5)
    assert [r["name"] for r in res] == ["Netflix"]
    assert res[0]["days_until"] == 2


def test_set_cancel_by():
    e = _monthly_exp("Trial", 0)
    s = _store_with([e])
    s.set_cancel_by(e["id"], "2026-06-27")
    assert s._find_def(e["id"])["cancel_by"] == "2026-06-27"
    s.set_cancel_by(e["id"], None)
    assert s._find_def(e["id"])["cancel_by"] is None


def test_set_note():
    e = _monthly_exp("Rent", 2000)
    s = _store_with([e])
    s.set_note(e["id"], "Landlord: 0400 000 000")
    assert s._find_def(e["id"])["note"] == "Landlord: 0400 000 000"


def test_rules_add_remove_recategorise():
    s = _store_with([_monthly_exp("Groceries", 0)])
    s.import_transactions(
        [{"date": "2026-06-01", "amount": -80, "description": "WOOLWORTHS METRO"}], "ANZ")
    # no rule yet → matches existing expense name "Groceries"? no; "woolworths" != names
    assert s.transactions()[0]["category"] == "Groceries" or \
        s.transactions()[0]["category"] is None
    s.add_rule("woolworths", "Food")          # re-categorises existing txns
    assert s.transactions()[0]["category"] == "Food"
    assert len(s.rules()) == 1
    s.remove_rule(0)
    assert s.rules() == []
    assert s.transactions()[0]["category"] != "Food"   # reverted on recategorise


def test_spend_by_tag():
    a = dm.item("Rent", 2000, type="expense", start="2026-06-01", recurrence=_MO,
                tags=["Fixed", "Home"])
    b = dm.item("Gym", 50, type="expense", start="2026-06-01", recurrence=_MO,
                tags=["Health"])
    c = dm.item("Misc", 30, type="expense", start="2026-06-01", recurrence=_MO)  # untagged
    inc = dm.item("Salary", 5000, type="income", start="2026-06-01", recurrence=_MO,
                  tags=["Work"])
    res = dict(B.spend_by_tag([a, b, c, inc], date(2026, 6, 1), date(2026, 6, 30)))
    assert res["Fixed"] == 2000 and res["Home"] == 2000   # multi-tag counts to each
    assert res["Health"] == 50
    assert res["(untagged)"] == 30
    assert "Work" not in res                               # income excluded


def test_bills_summary_and_set_paid():
    rent = dm.item("Rent", 2000, type="expense", start="2026-06-01", recurrence=_MO,
                   due="2026-06-01")
    wifi = dm.item("Wifi", 100, type="expense", start="2026-06-01", recurrence=_MO,
                   due="2026-06-20")
    s = _store_with([rent, wifi])
    today = date(2026, 6, 10)
    bs = B.bills_summary(s.items(), date(2026, 6, 1), date(2026, 6, 30), today)
    assert bs["due_count"] == 2 and bs["due_total"] == 2100
    assert bs["overdue"] == 1                      # Rent due Jun 1 < Jun 10
    assert bs["paid_count"] == 0

    s.set_paid(rent["id"], "2026-06-01", True)     # mark Rent paid (this occurrence)
    bs2 = B.bills_summary(s.items(), date(2026, 6, 1), date(2026, 6, 30), today)
    assert bs2["paid_count"] == 1 and bs2["due_count"] == 1 and bs2["overdue"] == 0
    # next month's occurrence is unpaid again
    bs3 = B.bills_summary(s.items(), date(2026, 7, 1), date(2026, 7, 31), today)
    assert bs3["paid_count"] == 0 and bs3["due_count"] == 2


def test_people_registry_and_membership():
    s = _store_with([])
    plan = s.create_shared_plan(
        "Spotify", 27.0, "expense", "2026-06-01",
        {"split": "even", "owner_pays": True, "members": [{"name": "Sam"}]}, _MO)
    assert any(p["name"] == "Sam" for p in s.people())   # auto-registered

    s.add_person("Alex")
    assert s.person_in_subs("Alex") == set()
    s.set_person_in_sub("Alex", plan["id"], True)
    assert plan["id"] in s.person_in_subs("Alex")
    # even split now 27 / (2 members + owner) = 9 each
    shares = {r["name"]: r["share"]
              for r in B.member_shares(s._find_def(plan["id"]), date(2026, 6, 1))}
    assert round(shares["Alex"], 2) == 9.0 and round(shares["Sam"], 2) == 9.0

    alex = next(p for p in s.people() if p["name"] == "Alex")
    s.remove_person(alex["id"])
    assert not any(p["name"] == "Alex" for p in s.people())
    assert plan["id"] not in s.person_in_subs("Alex")    # also removed from the plan


def test_calc_eval_arithmetic_for_shares():
    import widgets
    assert widgets.calc_eval("27/3") == 9.0
    assert widgets.calc_eval("10+5") == 15.0
    assert widgets.calc_eval("(20+4)/2") == 12.0
    assert widgets.calc_eval("nonsense") is None


def test_shared_plan_store_ops():
    s = _store_with([])
    plan = s.create_shared_plan(
        "Spotify", 27.0, "income", "2026-06-01",
        {"split": "even", "owner_pays": True,
         "members": [{"name": "Sam"}, {"name": "Alex"}]})
    assert s.shared_plans()[0]["name"] == "Spotify"
    assert B.all_paid(plan, date(2026, 6, 1)) is False
    s.set_member_paid(plan["id"], "2026-06-01", "Sam", True)
    s.set_member_paid(plan["id"], "2026-06-01", "Alex", True)
    assert B.all_paid(s._find_def(plan["id"]), date(2026, 6, 1)) is True


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t(); print(f"  PASS  {t.__name__}"); passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc(); failed += 1
    print(f"\n{passed} passed, {failed} failed")
