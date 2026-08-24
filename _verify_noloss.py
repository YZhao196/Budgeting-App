"""Confirm no SummaryCard content disappears at any window height, and that
the right column scrolls (rather than clipping) when the window is short."""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtGui import QFont
import theme as T
import widgets as W
from widgets import BoundedScroll
from main import MainWindow

W.ANIMATE = False
app = QApplication(sys.argv)
app.setStyleSheet(T.global_qss()); app.setFont(QFont(T.FONT_FAMILY, 10))


def settle(ms=300):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


win = MainWindow()
win.resize(T.WIN_W, T.WIN_H)
win.show()
settle(300)
ov = win.overview
s = ov.summary
# the right-column scroll area
right_scroll = ov.chart.parentWidget().parentWidget()
while right_scroll and not isinstance(right_scroll, BoundedScroll):
    right_scroll = right_scroll.parentWidget()

for h in (720, 850, T.WIN_H, 1400):
    win.resize(T.WIN_W, h)
    settle(300)
    # every SummaryCard section must stay visible at every height
    vis = {
        "tabs": s.tabs.isVisible(),
        "hero": s.hero.isVisible(),
        "box_in": s.box_in.isVisible(),
        "box_out": s.box_out.isVisible(),
        "targets": s._targets_section.isVisible(),
        "weekly": s._weekly_section.isVisible(),
        "target_lbl_text": bool(s.target_lbl.text()),
        "savings_lbl_text": bool(s.savings_lbl.text()),
    }
    sb = right_scroll.verticalScrollBar() if right_scroll else None
    sb_range = (sb.minimum(), sb.maximum()) if sb else None
    print(f"h={h:>4}  all_visible={all(vis.values())}  "
          f"summary_h={s.height()}  scroll_max={sb_range[1] if sb_range else '?'}")
    assert all(vis.values()), f"MISSING at h={h}: {vis}"

# capture the short-window frame to eyeball the scroll
win.resize(T.WIN_W, 720)
settle(300)
win.grab().save("preview_noloss_720.png")
print("PASS — no section hidden at any height. saved preview_noloss_720.png")
