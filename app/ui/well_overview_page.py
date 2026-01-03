# app/ui/well_overview_page.py
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame


class WellOverviewPage(QWidget):
    """
    WELL NAME click target page.

    Target behavior:
      - Show message: "Please select a subsection..."
      - English-only informational text (global rule).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Well Overview")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        subtitle = QLabel("Please select a subsection...")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)

        hint = QLabel(
            "Use the left navigation tree to open WELL IDENTITY, TRAJECTORY, HOLE SECTION, "
            "or a specific hole size section."
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(divider)
        layout.addWidget(hint)
        layout.addStretch(1)