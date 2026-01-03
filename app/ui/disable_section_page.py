# app/ui/disable_section_page.py
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame


class DisabledSectionPage(QWidget):
    """
    UI-only page shown when a hole size section is clicked but not enabled.

    Global rule:
      - English-only warnings/notes/info messages.
    """

    def __init__(
        self,
        message: str = "This section is not enabled. Please enable it under HOLE SECTION.",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Section Disabled")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)

        body = QLabel(message)
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        hint = QLabel("Go to HOLE SECTION and enable the desired hole size, then return to this section.")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        layout.addWidget(title)
        layout.addWidget(divider)
        layout.addWidget(body)
        layout.addWidget(hint)
        layout.addStretch(1)