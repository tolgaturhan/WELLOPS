import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.ui.main_windows import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    icon_path = Path(__file__).resolve().parent / "assets" / "icon" / "app.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    win = MainWindow()
    win.resize(1200, 800)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
