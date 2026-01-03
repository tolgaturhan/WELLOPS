import sys
from PySide6.QtWidgets import QApplication

from app.ui.main_windows import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1200, 800)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())