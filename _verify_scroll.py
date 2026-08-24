import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtGui import QFont
import theme as T
import widgets as W
from main import MainWindow

W.ANIMATE = False
app = QApplication(sys.argv)
app.setStyleSheet(T.global_qss()); app.setFont(QFont(T.FONT_FAMILY, 10))


def settle(ms=250):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


win = MainWindow()
win.resize(T.WIN_W, T.WIN_H)
win.show()
settle(300)
win.go("analytics")
settle(300)

ov = win.analytics._ov
scroll = ov.findChild(type(ov), None)  # not used; find the BoundedScroll directly
from widgets import BoundedScroll
sc = ov.findChild(BoundedScroll)
sb = sc.verticalScrollBar()
print("scroll range:", sb.minimum(), sb.maximum())
for frac in (0.35, 0.55, 0.75, 1.0):
    sb.setValue(int(sb.maximum() * frac))
    settle(150)
    win.grab().save(f"preview_scroll_{int(frac*100)}.png")
print("done")
