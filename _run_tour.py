"""Drive the real app across every page for a critique pass."""
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

for key in ("overview", "analytics", "goals", "history", "subscriptions", "settings"):
    win.go(key)
    settle(250)
    win.grab().save(f"tour_{key}.png")
    print(f"captured {key}")

# subscriptions -> People tab
win.go("subscriptions")
settle(150)
win.subs.tabbar.set_active("People")
win.subs._switch("People")
settle(150)
win.grab().save("tour_subs_people.png")
print("captured subs_people")

print("done")
