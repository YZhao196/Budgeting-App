"""Persistence layer.

Each month is a self-contained JSON document under ``data/months/YYYY_MM.json``
so the app can grow indefinitely without one giant file.  On first run we seed
five months (Jan–May 2026) – May matches the mock-up exactly, the earlier
months are scaled variations so the dashboard chart has real history to draw.
"""

from __future__ import annotations

import calendar
import copy
import json
import os
import sys
import uuid
from datetime import date, timedelta


def _app_dir() -> str:
    """Folder to keep the writable ``data/`` next to.

    When frozen by PyInstaller, ``__file__`` points inside a temp extraction
    dir, so anchor to the executable instead (keeps data beside the .exe)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DATA_DIR   = os.path.join(_app_dir(), "data")
MONTHS_DIR = os.path.join(DATA_DIR, "months")
GOALS_FILE = os.path.join(DATA_DIR, "goals.json")
ITEMS_FILE = os.path.join(DATA_DIR, "items.json")   # flat store (3a model)

MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
MONTH_ABBR  = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def new_id() -> str:
    return uuid.uuid4().hex[:8]


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _fname(year: int, month: int) -> str:
    return os.path.join(MONTHS_DIR, f"{year:04d}_{month:02d}.json")


def cat(name, amount=0.0, *, type="income", recurring=False,
        due=None, added="01-01", paid=False, note="", priority=0,
        repeat=None, expanded=False, expandable=False, children=None) -> dict:
    """Build one category record (a node in the income/expense tree)."""
    if repeat is None and recurring:
        repeat = {"type": "interval", "every": 1, "unit": "month"}
    return {
        "id": new_id(),
        "name": name,
        "type": type,
        "amount": float(amount),          # ignored for parents (derived from kids)
        "recurring": repeat is not None,  # derived from the repeat rule
        "repeat": repeat,                 # None | {"type":"interval"|"days", ...}
        "due": due,                        # ISO "YYYY-MM-DD" or None  (expenses)
        "added": added,                    # "MM-DD" — day determines which week this item belongs to
        "paid": paid,
        "priority": priority,             # 0 none · 1 high · 2 medium · 3 low
        "note": note,
        "expanded": expanded,
        "expandable": expandable or bool(children),   # shows a chevron
        "children": children or [],
    }


def goal(name: str, target: float, saved: float = 0.0) -> dict:
    """One named savings goal (lives app-wide, not per-month)."""
    return {"id": new_id(), "name": name,
            "target": float(target), "saved": float(saved)}


# account kinds: cash · savings · investment · asset (assets) | debt · credit (liabilities)
def account(name: str, kind: str = "cash", balance: float = 0.0,
            id=None, note: str = "") -> dict:
    return {"id": id or new_id(), "name": name, "kind": kind,
            "balance": float(balance), "note": note}


def _seed_goals() -> dict:
    return {"goals": [
        goal("Emergency fund", 10000, 4300),
        goal("New laptop", 2000, 1250),
        goal("Vacation", 5000, 800),
    ]}


# --------------------------------------------------------------------------- #
#  Seed data – the May 2026 mock-up
# --------------------------------------------------------------------------- #
def _seed_income() -> list:
    return [
        cat("Employment", 5300, recurring=True, added="01-01", expandable=True),
        cat("Resale", added="01-01", expanded=True, children=[
            cat("eBay", 250, recurring=True, added="01-01"),
            cat("Marketplace", 150, recurring=True, added="01-01"),
        ]),
        cat("Dividends", 180, recurring=True, added="01-01"),
        cat("Freelance", 0, added="01-01"),
    ]


def _seed_expenses() -> list:
    E = lambda *a, **k: cat(*a, type="expense", **k)
    return [
        E("Rent",          2000, recurring=True, due="2026-06-01", added="01-01",
          expandable=True, priority=1),
        E("Household",      250, added="01-01", expandable=True),
        E("Transport",      350, added="01-01", expandable=True),
        E("Electric",       150, recurring=True, due="2026-06-20", added="01-01",
          priority=2),
        E("Water",           50, recurring=True, added="01-01", priority=3),
        E("Wifi",           100, recurring=True, due="2026-06-15", added="01-01",
          priority=2),
        E("Subscriptions",   85, added="01-01"),
        E("Dining out",     200, added="01-01"),
        E("Health",         120, added="01-01"),
    ]


def _blank_month(year: int, month: int) -> dict:
    return {
        "month": month_key(year, month),
        "income": [],
        "expenses": [],
        "target_pnl": 600.0,
        "weekly_budget": 900.0,
        "weeks": 4,
        "currency": "$",
    }


def _scaled_expenses(base: list, factor: float) -> list:
    """Deep-copy expense tree with every leaf amount scaled (for past months)."""
    out = copy.deepcopy(base)
    for node in out:
        node["id"] = new_id()
        if node["children"]:
            for ch in node["children"]:
                ch["id"] = new_id()
                ch["amount"] = round(ch["amount"] * factor)
        else:
            node["amount"] = round(node["amount"] * factor)
    return out


def _leaf_total(nodes: list) -> float:
    """Sum leaf amounts (parents derive from children, so only leaves count)."""
    total = 0.0
    for n in nodes:
        if n.get("children"):
            total += _leaf_total(n["children"])
        else:
            total += float(n.get("amount", 0.0))
    return total


def _seed_all() -> None:
    """Create Jan–May 2026.  May is exact; earlier months hit target P&Ls."""
    income = _seed_income()
    base_expenses = _seed_expenses()

    # desired profit for each month -> implies a total-expense figure
    targets = {1: 3050, 2: 3500, 3: 3250, 4: 3600, 5: 2575}
    income_total = _leaf_total(income)
    base_exp_total = _leaf_total(base_expenses)

    for m, pnl in targets.items():
        doc = _blank_month(2026, m)
        doc["income"] = copy.deepcopy(income)
        for node in doc["income"]:
            node["id"] = new_id()
            for ch in node["children"]:
                ch["id"] = new_id()
        if m == 5:
            doc["expenses"] = base_expenses
        else:
            want_exp = income_total - pnl
            doc["expenses"] = _scaled_expenses(base_expenses,
                                               want_exp / base_exp_total)
        _write(doc)


# --------------------------------------------------------------------------- #
#  Disk I/O
# --------------------------------------------------------------------------- #
def _write(doc: dict) -> None:
    y, m = (int(x) for x in doc["month"].split("-"))
    with open(_fname(y, m), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)


class DataManager:
    """Loads / saves month documents and exposes the list of stored months."""

    def __init__(self) -> None:
        os.makedirs(MONTHS_DIR, exist_ok=True)
        self._cache: dict[tuple[int, int], dict] = {}

    # -- queries ---------------------------------------------------------- #
    def list_months(self) -> list[tuple[int, int]]:
        out = []
        for f in os.listdir(MONTHS_DIR):
            if f.endswith(".json") and "_" in f:
                try:
                    y, m = f[:-5].split("_")
                    out.append((int(y), int(m)))
                except ValueError:
                    continue
        return sorted(out)

    def has_month(self, year: int, month: int) -> bool:
        return os.path.exists(_fname(year, month))

    def load_month(self, year: int, month: int) -> dict:
        key = (year, month)
        if key in self._cache:
            return self._cache[key]
        if self.has_month(year, month):
            with open(_fname(year, month), "r", encoding="utf-8") as fh:
                doc = json.load(fh)
            self._cache[key] = doc
            return doc
        # brand-new month: carry forward recurring items from the latest month
        doc = _blank_month(year, month)
        prev = self._latest_before(year, month)
        if prev:
            src = self.load_month(*prev)
            doc["income"]   = _carry(src["income"], year, month)
            doc["expenses"] = _carry(src["expenses"], year, month)
            doc["target_pnl"]    = src.get("target_pnl", 600.0)
            doc["weekly_budget"] = src.get("weekly_budget", 900.0)
            doc["weeks"]         = src.get("weeks", 4)
        self.save_month(doc)
        return doc

    def save_month(self, doc: dict) -> None:
        y, m = (int(x) for x in doc["month"].split("-"))
        self._cache.pop((y, m), None)  # invalidate so next load re-reads
        _write(doc)

    def reset_all(self, year: int, month: int) -> None:
        """Delete every month file and goals file, then create one blank month."""
        self._cache.clear()
        for f in os.listdir(MONTHS_DIR):
            if f.endswith(".json"):
                try:
                    os.remove(os.path.join(MONTHS_DIR, f))
                except OSError:
                    pass
        if os.path.exists(GOALS_FILE):
            try:
                os.remove(GOALS_FILE)
            except OSError:
                pass
        doc = _blank_month(year, month)
        _write(doc)

    # -- savings goals (app-wide) ----------------------------------------- #
    def load_goals(self) -> dict:
        if not os.path.exists(GOALS_FILE):
            self.save_goals(_seed_goals())
        with open(GOALS_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def save_goals(self, data: dict) -> None:
        with open(GOALS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    # -- internal --------------------------------------------------------- #
    def _latest_before(self, year: int, month: int):
        earlier = [t for t in self.list_months() if t < (year, month)]
        return earlier[-1] if earlier else None


def _advance_due(due: str, year: int, month: int) -> str:
    """Move a due date into the target month, keeping the day (clamped)."""
    try:
        day = int(due[8:10]) if len(due) >= 10 else int(due.split("-")[1])
    except (ValueError, IndexError):
        return due
    day = min(day, calendar.monthrange(year, month)[1])
    return f"{year:04d}-{month:02d}-{day:02d}"


def _due_every_month(repeat) -> bool:
    """True for cadences that occur every month (so their due date should roll
    forward); False for every-N-month / yearly rules (keep the real next due)."""
    if not repeat:
        return True
    if repeat.get("type") == "days":
        return True
    if repeat.get("type") == "interval":
        unit = repeat.get("unit", "month")
        return unit in ("day", "week") or \
            (unit == "month" and int(repeat.get("every", 1)) == 1)
    return True


def _carry_one(node: dict, year: int, month: int) -> dict:
    c = copy.deepcopy(node)
    c["id"] = new_id()
    c["paid"] = False
    c["expanded"] = False
    if c.get("due") and _due_every_month(c.get("repeat")):
        c["due"] = _advance_due(c["due"], year, month)
    return c


def _carry(nodes: list, year: int, month: int) -> list:
    """Build the next month's tree: keep recurring leaves (and parents that have
    a recurring child), advance their due dates and reset per-month state.
    One-off (non-recurring) items are *not* carried forward."""
    out = []
    for n in nodes:
        kids = n.get("children") or []
        if kids:
            carried = [_carry_one(c, year, month) for c in kids
                       if c.get("recurring")]
            if not carried:
                continue
            parent = copy.deepcopy(n)
            parent["id"] = new_id()
            parent["paid"] = False
            parent["expanded"] = False
            parent["children"] = carried
            out.append(parent)
        elif n.get("recurring"):
            out.append(_carry_one(n, year, month))
    return out


# =========================================================================== #
#  FLAT-STORE MODEL (3a) — item definitions, migration, ItemStore
#
#  A definition is one item stored once: a start date, an optional recurrence
#  rule, and a dict of per-occurrence overrides.  Views are produced by the
#  occurrence engine in ``backend`` expanding definitions over a date range.
# =========================================================================== #
def item(name, amount=0.0, *, type="income", start=None, end=None,
         recurrence=None, due=None, priority=0, note="", children=None,
         overrides=None, id=None, expanded=False, expandable=False,
         ideal=0.0, tags=None, shared=None, subscription=False,
         cancel_by=None) -> dict:
    """Build one item definition (a node in the flat-store tree)."""
    return {
        "id":         id or new_id(),
        "name":       name,
        "type":       type,                 # "income" | "expense"
        "amount":     float(amount),        # actual amount (parents derive from kids)
        "ideal":      float(ideal or 0.0),  # ideal/budget monthly amount (expenses)
        "cancel_by":  cancel_by,            # ISO date — free-trial / cancel-by deadline
        "start":      start,                # ISO "YYYY-MM-DD" — first possible occurrence
        "end":        end,                  # ISO date | None — last possible occurrence
        "recurrence": recurrence,           # None | {"type":"interval"|"days", ...}
        "due":        due,                  # default due (ISO) | None
        "priority":   priority,
        "note":       note,
        "tags":       list(tags) if tags else [],
        "shared":     shared,               # None | {split, owner_pays, members:[{name,share?}]}
        "subscription": bool(subscription), # user-flagged "my subscription" (outgoing)
        "expanded":   expanded,
        "expandable": expandable or bool(children),
        "children":   children or [],
        "overrides":  overrides or {},      # {occ_date_iso:{amount?,due?,paid?,skipped?,member_paid?}}
    }


# --------------------------------------------------------------------------- #
#  Migration: month documents  ->  flat item definitions
# --------------------------------------------------------------------------- #
def _find_by_path(doc: dict, doc_key: str, path: tuple) -> dict | None:
    """Walk a month doc's income/expense tree following a tuple of names."""
    nodes = doc.get(doc_key, [])
    node = None
    for name in path:
        node = next((n for n in nodes if n.get("name") == name), None)
        if node is None:
            return None
        nodes = node.get("children") or []
    return node


def _merged_top(docs, months, doc_key):
    """Union of top-level node names across every month (latest month sets the
    order; items seen only in earlier months are appended). Returns
    (ordered_names, info) where info[name] = {parent, children:[names], expanded}."""
    order: list = []
    info: dict = {}
    for (y, m) in reversed(months):                   # latest first → preferred order
        for n in docs[(y, m)].get(doc_key, []):
            nm = n.get("name")
            if nm not in info:
                info[nm] = {"parent": False, "children": [], "_cset": set(),
                            "expanded": bool(n.get("expanded"))}
                order.append(nm)
            kids = n.get("children") or []
            if kids:
                info[nm]["parent"] = True
                for c in kids:
                    cn = c.get("name")
                    if cn not in info[nm]["_cset"]:
                        info[nm]["_cset"].add(cn)
                        info[nm]["children"].append(cn)
    return order, info


def _series_day(node: dict) -> int:
    """Day-of-month to anchor a migrated item's occurrences to: its due day if
    present, else its added day, else the 1st. Keeps weeks meaningful."""
    due = node.get("due")
    if due and len(str(due)) >= 10:
        try:
            d = int(str(due)[8:10])
            if 1 <= d <= 31:
                return d
        except ValueError:
            pass
    added = node.get("added")
    if added:
        try:
            d = int(str(added).split("-")[-1])
            if 1 <= d <= 31:
                return d
        except ValueError:
            pass
    return 1


def _convert_leaf(doc_key, item_type, path, docs, months) -> dict:
    """Convert a leaf (by name-path) into a definition, capturing every month it
    appears in as overrides so historical amounts are reproduced exactly."""
    present = [(y, m, _find_by_path(docs[(y, m)], doc_key, path))
               for (y, m) in months]
    present = [(y, m, nd) for (y, m, nd) in present if nd is not None]
    name = path[-1]
    if not present:
        return item(name, 0.0, type=item_type)

    fy, fm, _ = present[0]
    ly, lm, lastnd = present[-1]
    recurring = any(nd.get("recurring") for (_, _, nd) in present)
    day = _series_day(lastnd)          # anchor occurrences to the item's due/added day
    def _key(y, m):                    # occurrence date for month, clamped to its length
        return f"{y:04d}-{m:02d}-{min(day, calendar.monthrange(y, m)[1]):02d}"
    start = _key(fy, fm)
    end = None if recurring else \
        f"{ly:04d}-{lm:02d}-{calendar.monthrange(ly, lm)[1]:02d}"
    base_amount   = float(lastnd.get("amount", 0.0))
    base_due      = lastnd.get("due")
    base_priority = lastnd.get("priority", 0) or 0

    overrides: dict = {}
    present_keys = {(y, m) for (y, m, _) in present}
    for (y, m, nd) in present:
        ov = {}
        if float(nd.get("amount", 0.0)) != base_amount:
            ov["amount"] = float(nd.get("amount", 0.0))
        if nd.get("due") != base_due:
            ov["due"] = nd.get("due")
        if nd.get("paid"):
            ov["paid"] = True
        if (nd.get("priority", 0) or 0) != base_priority:
            ov["priority"] = nd.get("priority", 0) or 0
        if ov:
            overrides[_key(y, m)] = ov
    # interior gaps -> explicit skip so monthly recurrence doesn't invent amounts
    yy, mm = fy, fm
    while (yy, mm) <= (ly, lm):
        if (yy, mm) not in present_keys:
            overrides[_key(yy, mm)] = {"skipped": True}
        idx = yy * 12 + (mm - 1) + 1
        yy, mm = idx // 12, idx % 12 + 1

    return item(name, base_amount, type=item_type, start=start, end=end,
                recurrence={"type": "interval", "every": 1, "unit": "month"},
                due=base_due, priority=base_priority, overrides=overrides,
                expandable=bool(lastnd.get("expandable")),
                expanded=bool(lastnd.get("expanded")))


def _migrate_months_to_items(manager) -> dict:
    """Build the flat store from existing month documents (preserves all numbers).
    Structure is the union of every month's tree so items that only appear in some
    months (e.g. non-recurring ones dropped by carry-forward) are not lost."""
    months = manager.list_months()
    docs = {(y, m): manager.load_month(y, m) for (y, m) in months}
    currency = "$"
    period_settings: dict = {}
    for (y, m) in months:
        d = docs[(y, m)]
        period_settings[month_key(y, m)] = {
            "target_pnl":    d.get("target_pnl", 600.0),
            "weekly_budget": d.get("weekly_budget", 900.0),
        }
        currency = d.get("currency", currency)

    items: list = []
    for doc_key, item_type in (("income", "income"), ("expenses", "expense")):
        order, info = _merged_top(docs, months, doc_key)
        for nm in order:
            meta = info[nm]
            if meta["parent"]:
                kids = [_convert_leaf(doc_key, item_type, (nm, cn), docs, months)
                        for cn in meta["children"]]
                starts = [k["start"] for k in kids if k.get("start")]
                items.append(item(nm, 0.0, type=item_type,
                                  start=min(starts) if starts else None,
                                  recurrence=None, children=kids, expandable=True,
                                  expanded=meta["expanded"]))
            else:
                items.append(_convert_leaf(doc_key, item_type, (nm,), docs, months))
    return {
        "items":           items,
        "settings":        {"currency": currency, "time_lens": "iso_week"},
        "period_settings": period_settings,
    }


def _default_settings() -> dict:
    return {"currency": "$", "time_lens": "iso_week"}


class ItemStore:
    """Loads / saves the flat item store, migrating month files on first run."""

    def __init__(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        self._data: dict | None = None

    # -- load / save ------------------------------------------------------ #
    def load(self) -> dict:
        if self._data is not None:
            return self._data
        if os.path.exists(ITEMS_FILE):
            with open(ITEMS_FILE, "r", encoding="utf-8") as fh:
                self._data = json.load(fh)
        else:
            mgr = DataManager()
            if not mgr.list_months():     # brand-new install → seed demo months first
                _seed_all()
                mgr = DataManager()
            self._data = _migrate_months_to_items(mgr)
            self.save()
        self._data.setdefault("settings", _default_settings())
        self._data.setdefault("period_settings", {})
        self._data.setdefault("items", [])
        self._data.setdefault("transactions", [])   # imported bank transactions
        self._data.setdefault("rules", [])          # {match, category, tags} categorisation
        self._data.setdefault("people", [])         # people registry (shared-plan members)
        self._data.setdefault("accounts", [])       # net-worth accounts (cash/asset/debt)
        return self._data

    def save(self) -> None:
        with open(ITEMS_FILE, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    # -- queries ---------------------------------------------------------- #
    def items(self) -> list:
        return self.load()["items"]

    def settings(self) -> dict:
        return self.load()["settings"]

    def currency(self) -> str:
        return self.settings().get("currency", "$")

    def time_lens(self) -> str:
        return self.settings().get("time_lens", "iso_week")

    def set_time_lens(self, lens: str) -> None:
        self.settings()["time_lens"] = lens
        self.save()

    def period_settings(self, year: int, month: int) -> dict:
        ps = self.load()["period_settings"]
        return ps.setdefault(month_key(year, month),
                             {"target_pnl": 600.0, "weekly_budget": 900.0})

    def set_period_setting(self, year: int, month: int, key: str, value) -> None:
        self.period_settings(year, month)[key] = value
        self.save()

    # -- synthesized "documents" (DataManager-compatible read interface) --- #
    def synth_doc(self, rstart: date, rend: date, year: int, month: int,
                  label: str | None = None) -> dict:
        """A month/range view shaped like the legacy month document so the
        existing widgets can render it. Amounts are resolved for [rstart, rend]."""
        import backend as B            # lazy: avoids import cycle at module load
        inc, exp = B.view_nodes(self.items(), rstart, rend)
        ps = self.period_settings(year, month)
        return {
            "month":         month_key(year, month),
            "range_start":   rstart.isoformat(),
            "range_end":     rend.isoformat(),
            "label":         label,
            "income":        inc,
            "expenses":      exp,
            "target_pnl":    ps.get("target_pnl", 600.0),
            "weekly_budget": ps.get("weekly_budget", 900.0),
            "weeks":         4,
            "currency":      self.currency(),
        }

    def load_month(self, year: int, month: int) -> dict:
        last = calendar.monthrange(year, month)[1]
        return self.synth_doc(date(year, month, 1), date(year, month, last),
                              year, month)

    def load_range(self, rstart: date, rend: date, label: str | None = None) -> dict:
        # period settings keyed by the month the range starts in
        return self.synth_doc(rstart, rend, rstart.year, rstart.month, label)

    def _earliest_start(self) -> date:
        starts = []
        def scan(nodes):
            for n in nodes:
                if n.get("children"):
                    scan(n["children"])
                elif n.get("start"):
                    starts.append(n["start"])
        scan(self.items())
        if not starts:
            t = date.today()
            return date(t.year, t.month, 1)
        y, m, *_ = min(starts).split("-")
        return date(int(y), int(m), 1)

    def list_months(self) -> list[tuple[int, int]]:
        """Months from the earliest item start through the current month."""
        first = self._earliest_start()
        today = date.today()
        out, idx = [], first.year * 12 + (first.month - 1)
        end = today.year * 12 + (today.month - 1)
        while idx <= end:
            out.append((idx // 12, idx % 12 + 1))
            idx += 1
        return out

    def has_month(self, year: int, month: int) -> bool:
        return (year, month) in set(self.list_months())

    # -- edit operations (definition-level; scope-aware) ------------------- #
    def _find_def(self, def_id: str):
        def scan(nodes):
            for n in nodes:
                if n.get("id") == def_id:
                    return n
                if n.get("children"):
                    r = scan(n["children"])
                    if r:
                        return r
            return None
        return scan(self.items())

    def _find_parent_list(self, def_id: str):
        """Return the list that directly contains def_id (for insert/remove)."""
        def scan(nodes):
            for n in nodes:
                if n.get("id") == def_id:
                    return nodes
                if n.get("children"):
                    r = scan(n["children"])
                    if r is not None:
                        return r
            return None
        return scan(self.items())

    def edit_field(self, def_id: str, occ_iso: str | None, field: str,
                   value, scope: str = "instance") -> None:
        """Apply an edit to a definition with the chosen scope.
        scope: 'instance' (this occurrence) | 'future' (this + later) | 'all'."""
        defn = self._find_def(def_id)
        if defn is None:
            return
        if field == "name" or scope == "all":
            defn[field] = value
            for ov in defn.get("overrides", {}).values():
                ov.pop(field, None)
        elif scope == "future" and occ_iso:
            self._split_future(defn, occ_iso, {field: value})
        else:                                   # instance
            if occ_iso:
                defn.setdefault("overrides", {}).setdefault(occ_iso, {})[field] = value
            else:
                defn[field] = value
        self.save()

    def set_paid(self, def_id: str, occ_iso: str, paid: bool) -> None:
        defn = self._find_def(def_id)
        if defn is None or not occ_iso:
            return
        ov = defn.setdefault("overrides", {}).setdefault(occ_iso, {})
        ov["paid"] = paid
        self.save()

    def _split_future(self, defn: dict, occ_iso: str, changes: dict) -> None:
        """End the series the day before occ_iso and start a new one with changes."""
        occ = date.fromisoformat(occ_iso)
        defn["end"] = (occ - timedelta(days=1)).isoformat()
        new = copy.deepcopy(defn)
        new["id"] = new_id()
        new["start"] = occ_iso
        new["end"] = None
        new.update(changes)
        # keep only overrides on/after the split for the new series
        new["overrides"] = {k: v for k, v in (defn.get("overrides") or {}).items()
                            if k >= occ_iso}
        defn["overrides"] = {k: v for k, v in (defn.get("overrides") or {}).items()
                             if k < occ_iso}
        siblings = self._find_parent_list(defn["id"])
        if siblings is not None:
            siblings.insert(siblings.index(defn) + 1, new)

    def add_top(self, item_type: str, start_iso: str) -> dict:
        defn = item("New item", 0.0, type=item_type, start=start_iso,
                    recurrence={"type": "interval", "every": 1, "unit": "month"})
        self.items().append(defn)
        self.save()
        return defn

    def add_child(self, parent_id: str, item_type: str, start_iso: str) -> dict | None:
        parent = self._find_def(parent_id)
        if parent is None:
            return None
        child = item("New item", 0.0, type=item_type, start=start_iso,
                     recurrence={"type": "interval", "every": 1, "unit": "month"})
        parent.setdefault("children", []).append(child)
        parent["expandable"] = True
        parent["expanded"] = True
        self.save()
        return child

    def delete_def(self, def_id: str) -> None:
        siblings = self._find_parent_list(def_id)
        if siblings is None:
            return
        defn = next((n for n in siblings if n.get("id") == def_id), None)
        if defn is not None:
            siblings.remove(defn)
        self.save()

    def delete_occurrence(self, def_id: str, occ_iso: str | None,
                          scope: str = "all") -> None:
        """Remove occurrences of a definition. scope: 'single' (skip just this
        occurrence) | 'future' (end the series here) | 'all' (delete it)."""
        defn = self._find_def(def_id)
        if defn is None:
            return
        if scope == "all" or not occ_iso:
            self.delete_def(def_id)
            return
        if scope == "future":
            defn["end"] = (date.fromisoformat(occ_iso) - timedelta(days=1)).isoformat()
        else:                                   # single occurrence
            defn.setdefault("overrides", {}).setdefault(occ_iso, {})["skipped"] = True
        self.save()

    def clear_type(self, item_type: str) -> None:
        """Delete every top-level definition of a given type (income/expense)."""
        data = self.load()
        data["items"] = [n for n in data["items"] if n.get("type") != item_type]
        self.save()

    def set_recurrence(self, def_id: str, recurrence) -> None:
        defn = self._find_def(def_id)
        if defn is not None:
            defn["recurrence"] = recurrence
            self.save()

    def set_ideal(self, def_id: str, value: float) -> None:
        defn = self._find_def(def_id)
        if defn is not None:
            defn["ideal"] = float(value)
            self.save()

    def set_note(self, def_id: str, note: str) -> None:
        defn = self._find_def(def_id)
        if defn is not None:
            defn["note"] = note
            self.save()

    def set_cancel_by(self, def_id: str, iso: str | None) -> None:
        defn = self._find_def(def_id)
        if defn is not None:
            defn["cancel_by"] = iso or None
            self.save()

    # -- net-worth accounts ----------------------------------------------- #
    def accounts(self) -> list:
        return self.load().setdefault("accounts", [])

    def add_account(self, name: str, kind: str = "cash",
                    balance: float = 0.0) -> dict:
        acc = account(name, kind, balance)
        self.accounts().append(acc)
        self.save()
        return acc

    def update_account(self, acc_id: str, **fields) -> None:
        a = next((x for x in self.accounts() if x.get("id") == acc_id), None)
        if a is not None:
            for k, v in fields.items():
                a[k] = v
            self.save()

    def remove_account(self, acc_id: str) -> None:
        accs = self.accounts()
        a = next((x for x in accs if x.get("id") == acc_id), None)
        if a is not None:
            accs.remove(a)
            self.save()

    # -- net-worth history (point-in-time snapshots) ---------------------- #
    def networth_history(self) -> list:
        return self.load().setdefault("networth_history", [])

    def snapshot_net_worth(self, today) -> None:
        """Record today's assets / liabilities once per day so the net-worth
        area chart accumulates real history over time."""
        import backend as B
        hist = self.networth_history()
        stamp = today.isoformat()
        if hist and hist[-1].get("date") == stamp:
            return
        nw = B.net_worth(self.accounts())
        hist.append({"date": stamp, "assets": nw["assets"],
                     "liabilities": nw["liabilities"]})
        self.save()

    def set_tags(self, def_id: str, tags: list) -> None:
        defn = self._find_def(def_id)
        if defn is not None:
            # de-duplicate, drop blanks, preserve order
            seen, clean = set(), []
            for t in tags:
                t = str(t).strip()
                if t and t.lower() not in seen:
                    seen.add(t.lower()); clean.append(t)
            defn["tags"] = clean
            self.save()

    def all_tags(self) -> list:
        """Every distinct tag currently in use, sorted."""
        found = set()
        def scan(nodes):
            for n in nodes:
                for t in n.get("tags", []):
                    found.add(t)
                if n.get("children"):
                    scan(n["children"])
        scan(self.items())
        return sorted(found, key=str.lower)

    # -- imported bank transactions --------------------------------------- #
    def transactions(self) -> list:
        return self.load()["transactions"]

    def rules(self) -> list:
        return self.load()["rules"]

    def _expense_names(self) -> list:
        names = []
        def scan(nodes):
            for n in nodes:
                if n.get("type") == "expense" or n.get("type") is None:
                    names.append(n.get("name", ""))
                if n.get("children"):
                    scan(n["children"])
        scan([n for n in self.items() if n.get("type") == "expense"])
        return [s for s in names if s]

    def categorise(self, description: str) -> tuple[str | None, list]:
        """(category, tags) for a transaction description: user rules first, then
        a fall-back substring match against existing expense category names."""
        d = (description or "").lower()
        for r in self.rules():
            if r.get("match") and r["match"].lower() in d:
                return r.get("category"), list(r.get("tags", []))
        for name in self._expense_names():
            if name and name.lower() in d:
                return name, []
        return None, []

    @staticmethod
    def _fingerprint(t: dict) -> tuple:
        return (t.get("date"), round(float(t.get("amount", 0)), 2),
                (t.get("description") or "").strip().lower(), t.get("account"))

    def import_transactions(self, raw: list, account: str = "ANZ") -> dict:
        """Add parsed transactions (skipping duplicates) and auto-categorise.
        Returns {added, skipped, categorised}."""
        txns = self.transactions()
        existing = {self._fingerprint(t) for t in txns}
        added = skipped = categorised = 0
        for rt in raw:
            t = {"id": new_id(), "date": rt["date"],
                 "amount": float(rt["amount"]),
                 "description": rt.get("description", ""),
                 "account": account}
            fp = self._fingerprint(t)
            if fp in existing:
                skipped += 1
                continue
            cat, tags = self.categorise(t["description"])
            t["category"], t["tags"] = cat, tags
            if cat:
                categorised += 1
            txns.append(t)
            existing.add(fp)
            added += 1
        self.save()
        return {"added": added, "skipped": skipped, "categorised": categorised}

    def recategorise_all(self) -> None:
        for t in self.transactions():
            cat, tags = self.categorise(t.get("description", ""))
            t["category"], t["tags"] = cat, tags
        self.save()

    def set_transaction_category(self, txn_id: str, category: str | None) -> None:
        for t in self.transactions():
            if t.get("id") == txn_id:
                t["category"] = category
                self.save()
                return

    def add_rule(self, match: str, category: str, tags: list | None = None) -> None:
        self.rules().append({"match": match, "category": category,
                             "tags": list(tags or [])})
        self.recategorise_all()

    def remove_rule(self, index: int) -> None:
        rules = self.rules()
        if 0 <= index < len(rules):
            rules.pop(index)
            self.recategorise_all()

    def clear_transactions(self) -> None:
        self.load()["transactions"] = []
        self.save()

    def set_expanded(self, def_id: str, value: bool) -> None:
        defn = self._find_def(def_id)
        if defn is not None:
            defn["expanded"] = value
            self.save()

    # -- shared plans (subscriptions split across members / clients) ------- #
    def shared_plans(self) -> list:
        """Top-level definitions that have a shared-payment config."""
        return [n for n in self.items() if n.get("shared")]

    def recurring_expenses(self) -> list:
        """Recurring, non-shared expense definitions (candidates to flag as subs)."""
        return [n for n in self.items()
                if n.get("type") == "expense" and n.get("recurrence")
                and not n.get("shared")]

    def subscriptions(self) -> list:
        """Expense definitions the user has flagged as their own subscriptions."""
        return [n for n in self.items()
                if n.get("subscription") and not n.get("shared")]

    def all_subscriptions(self) -> list:
        """Everything the subscription manager owns: solo flagged subs + shared plans."""
        return [n for n in self.items() if n.get("shared") or n.get("subscription")]

    def set_subscription(self, def_id: str, value: bool) -> None:
        defn = self._find_def(def_id)
        if defn is not None:
            defn["subscription"] = bool(value)
            self.save()

    def update_subscription(self, def_id: str, name: str, amount: float,
                            item_type: str, recurrence: dict,
                            shared, subscription: bool) -> None:
        """Edit an existing subscription's core properties in place."""
        defn = self._find_def(def_id)
        if defn is None:
            return
        defn["name"] = name
        defn["amount"] = float(amount)
        defn["type"] = item_type
        defn["recurrence"] = recurrence
        defn["shared"] = shared
        defn["subscription"] = bool(subscription)
        for m in (shared or {}).get("members", []):
            self._ensure_person(m.get("name"))
        self.save()

    def create_subscription(self, name: str, amount: float, start_iso: str,
                            recurrence: dict | None = None) -> dict:
        """A solo subscription you pay (no members)."""
        defn = item(name, amount, type="expense", start=start_iso,
                    recurrence=recurrence or {"type": "interval", "every": 1,
                                              "unit": "month"},
                    subscription=True)
        self.items().append(defn)
        self.save()
        return defn

    def set_shared(self, def_id: str, shared) -> None:
        defn = self._find_def(def_id)
        if defn is not None:
            defn["shared"] = shared
            self.save()

    def set_member_paid(self, def_id: str, occ_iso: str,
                        member: str, paid: bool) -> None:
        defn = self._find_def(def_id)
        if defn is None or not occ_iso:
            return
        ov = defn.setdefault("overrides", {}).setdefault(occ_iso, {})
        mp = ov.setdefault("member_paid", {})
        mp[member] = bool(paid)
        self.save()

    def create_shared_plan(self, name: str, amount: float, item_type: str,
                           start_iso: str, shared: dict,
                           recurrence: dict | None = None) -> dict:
        defn = item(name, amount, type=item_type, start=start_iso,
                    recurrence=recurrence or {"type": "interval", "every": 1,
                                              "unit": "month"},
                    shared=shared)
        self.items().append(defn)
        for m in (shared or {}).get("members", []):     # register everyone in the plan
            self._ensure_person(m.get("name"))
        self.save()
        return defn

    def update_subscription(self, def_id: str, *, name=None, amount=None,
                            item_type=None, recurrence=None, shared=False,
                            start=None) -> None:
        """Edit an existing subscription's properties in place.

        ``shared`` defaults to the sentinel ``False`` (leave as-is); pass a dict
        to make it a split/income plan, or ``None`` to make it solo."""
        defn = self._find_def(def_id)
        if defn is None:
            return
        if name is not None:
            defn["name"] = name
        if amount is not None:
            defn["amount"] = float(amount)
        if item_type is not None:
            defn["type"] = item_type
        if recurrence is not None:
            defn["recurrence"] = recurrence
        if start is not None:
            defn["start"] = start
        if shared is not False:
            if shared:
                defn["shared"] = shared
                for m in shared.get("members", []):
                    self._ensure_person(m.get("name"))
            else:
                defn.pop("shared", None)
        self.save()

    # -- people registry (each is a JSON record; drives who's in what) ----- #
    def people(self) -> list:
        return self.load().setdefault("people", [])

    def _ensure_person(self, name) -> None:
        name = (name or "").strip()
        if not name:
            return
        ppl = self.load().setdefault("people", [])
        if not any(p.get("name", "").lower() == name.lower() for p in ppl):
            ppl.append({"id": new_id(), "name": name, "note": ""})

    def add_person(self, name: str) -> dict | None:
        name = (name or "").strip()
        if not name:
            return None
        existing = next((p for p in self.people()
                         if p.get("name", "").lower() == name.lower()), None)
        if existing:
            return existing
        self._ensure_person(name)
        self.save()
        return self.people()[-1]

    def remove_person(self, person_id: str) -> None:
        ppl = self.people()
        person = next((p for p in ppl if p.get("id") == person_id), None)
        if not person:
            return
        name = person["name"]
        ppl.remove(person)
        for defn in self.items():                       # drop them from every plan
            sh = defn.get("shared")
            if sh and sh.get("members"):
                sh["members"] = [m for m in sh["members"] if m.get("name") != name]
        self.save()

    def person_in_subs(self, name: str) -> set:
        """Ids of the shared plans this person is currently a member of."""
        out = set()
        for defn in self.items():
            sh = defn.get("shared")
            if sh and any(m.get("name") == name for m in (sh.get("members") or [])):
                out.add(defn["id"])
        return out

    def set_person_in_sub(self, name: str, sub_id: str, member: bool) -> None:
        """Add or remove a person from a shared plan's member list."""
        defn = self._find_def(sub_id)
        if not defn or not defn.get("shared"):
            return
        members = defn["shared"].setdefault("members", [])
        has = any(m.get("name") == name for m in members)
        if member and not has:
            m = {"name": name}
            if defn["shared"].get("split") == "custom":
                m["share"] = 0.0
            members.append(m)
        elif not member and has:
            defn["shared"]["members"] = [m for m in members if m.get("name") != name]
        self.save()

    def reset_all(self, year: int, month: int) -> None:
        # keep a one-shot backup (<file>.bak) instead of deleting outright
        for f in (ITEMS_FILE, GOALS_FILE):
            if os.path.exists(f):
                try:
                    os.replace(f, f + ".bak")
                except OSError:
                    pass
        self._data = {"items": [], "settings": _default_settings(),
                      "period_settings": {}, "transactions": [], "rules": [],
                      "people": [], "accounts": []}
        self.save()

    # -- savings goals (app-wide, unchanged store) ------------------------ #
    def load_goals(self) -> dict:
        if not os.path.exists(GOALS_FILE):
            self.save_goals(_seed_goals())
        with open(GOALS_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def save_goals(self, data: dict) -> None:
        with open(GOALS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
