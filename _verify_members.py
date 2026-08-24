"""Drive SharedPlanDialog's new checkbox member picker."""
import sys
from PyQt6.QtWidgets import QApplication, QFrame
from PyQt6.QtGui import QFont
import theme as T
import datamanagement as dm
from widgets import SharedPlanDialog

app = QApplication(sys.argv)
app.setStyleSheet(T.global_qss()); app.setFont(QFont(T.FONT_FAMILY, 10))
store = dm.ItemStore(); store.load()
print("registry people:", [p["name"] for p in store.people()])

# 1. NEW split subscription: rows come from the registry, tick two, save
d = SharedPlanDialog(None, "$", store=store)
d.name.setText("Spotify Family"); d.amount.setValue(18)
d.kind.setCurrentIndex(1)          # I pay & split
d._sync()
print("member rows:", [r["name"] for r in d._mem_rows])
assert d._mem_rows, "no checkbox rows built from registry"
# tick the first two
for r in d._mem_rows[:2]:
    r["cb"].setChecked(True)
d._sync()
print("even-split hint:", d.hint.text())
d._save()
res = d._result
print("saved members:", res["shared"]["members"], "| split:", res["shared"]["split"])
names = [m["name"] for m in res["shared"]["members"]]
assert names == [d._mem_rows[0]["name"], d._mem_rows[1]["name"]]
assert all("share" not in m for m in res["shared"]["members"])  # even → no share

# 2. CUSTOM split: per-row share spinboxes appear, values captured
d2 = SharedPlanDialog(None, "$", store=store)
d2.name.setText("House wifi"); d2.amount.setValue(90)
d2.kind.setCurrentIndex(1); d2.split.setCurrentIndex(1)   # custom
d2._sync()
assert not d2._mem_rows[0]["spin"].isHidden(), "share spinbox hidden for custom split"
d2._mem_rows[0]["cb"].setChecked(True); d2._mem_rows[0]["spin"].setValue(30)
d2._mem_rows[1]["cb"].setChecked(True); d2._mem_rows[1]["spin"].setValue(30)
d2._save()
mem2 = d2._result["shared"]["members"]
print("custom members:", mem2)
assert all("share" in m for m in mem2) and mem2[0]["share"] == 30.0

# 3. EDIT prefill: existing members come back ticked with shares
existing = {
    "name": "Spotify Family", "type": "expense", "amount": 18,
    "start": "2026-01-01",
    "recurrence": {"type": "interval", "every": 1, "unit": "month"},
    "shared": {"split": "custom", "owner_pays": False,
               "members": [{"name": "Sam", "share": 9.0},
                           {"name": "Ghost McNotInRegistry", "share": 9.0}]},
}
d3 = SharedPlanDialog(None, "$", existing=existing, store=store)
ticked = {r["name"]: r["spin"].value() for r in d3._checked_members()}
print("prefilled ticked:", ticked)
assert "Sam" in ticked and ticked["Sam"] == 9.0
assert "Ghost McNotInRegistry" in ticked, "member absent from registry was dropped"

# 4. solo hides the whole member list
d4 = SharedPlanDialog(None, "$", store=store)
d4.kind.setCurrentIndex(0); d4._sync()
assert d4._mem_scroll.isHidden() and d4._new_person_btn.isHidden()

# screenshot the split dialog with rows
d5 = SharedPlanDialog(None, "$", store=store)
d5.name.setText("Spotify Family"); d5.kind.setCurrentIndex(1); d5._sync()
d5.resize(420, d5.sizeHint().height())
d5.show(); app.processEvents()
d5.grab().save("preview_members.png"); d5.hide()
print("PASS — checkbox member picker works. saved preview_members.png")
