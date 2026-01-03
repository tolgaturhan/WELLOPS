# app/ui/widgets/decimal_line_edit.py
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QLineEdit


class DecimalLineEdit(QLineEdit):
    """
    Numeric input with comma->dot normalization.

    Behavior:
      - Allows only numbers (with optional decimal separator '.' or ',')
      - On editingFinished:
          * trims spaces
          * replaces ',' with '.'
          * collapses multiple separators (best-effort)
      - Emits normalized(value_str) after normalization.

    Notes:
      - This is UI-only friendly; validation rules are enforced by hole_section_rules.py.
      - Use set_min_value(...) and set_allow_empty(...) for UX constraints,
        but final enforcement should still be in rules.
    """

    normalized = Signal(str)

    def __init__(self, parent: Optional[object] = None) -> None:
        super().__init__(parent)

        self._allow_empty: bool = True
        self._min_value: Optional[float] = None
        self._min_strict: bool = False

        # Validator accepts dot decimals. We still normalize commas into dots.
        v = QDoubleValidator(self)
        v.setNotation(QDoubleValidator.StandardNotation)
        # Do not over-constrain ranges here; rules module will enforce min/max.
        v.setBottom(-1e18)
        v.setTop(1e18)
        self.setValidator(v)

        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.editingFinished.connect(self._normalize_now)

    # -------------------------
    # Configuration
    # -------------------------
    def set_allow_empty(self, allow: bool) -> None:
        self._allow_empty = bool(allow)

    def set_min_value(self, min_value: Optional[float], *, strict: bool = False) -> None:
        self._min_value = min_value
        self._min_strict = bool(strict)

    # -------------------------
    # Core behavior
    # -------------------------
    def _normalize_now(self) -> None:
        raw = (self.text() or "").strip()

        if not raw:
            if self._allow_empty:
                self.setText("")
                self.normalized.emit("")
            else:
                # Leave empty; actual error message handled by rules
                self.setText("")
                self.normalized.emit("")
            return

        # Replace comma with dot
        s = raw.replace(" ", "").replace(",", ".")
        # If multiple dots appear, keep first as decimal separator and remove others
        if s.count(".") > 1:
            first = s.find(".")
            s = s[: first + 1] + s[first + 1 :].replace(".", "")

        # If it ends with ".", keep it as user intent? We normalize to remove trailing dot.
        if s.endswith("."):
            s = s[:-1]

        # Best-effort float parse
        try:
            x = float(s)
        except Exception:
            # If invalid, keep normalized string and let rule layer complain.
            self.setText(s)
            self.normalized.emit(s)
            return

        # Optional UX constraint (do not block typing; just keep normalized)
        if self._min_value is not None:
            if self._min_strict and not (x > self._min_value):
                # Keep as is; rule layer will raise error with proper message
                pass
            elif not self._min_strict and not (x >= self._min_value):
                pass

        # Keep minimal representation while preserving decimals if user entered them.
        # We do not force fixed decimals here.
        # Convert -0.0 to 0
        if x == 0:
            x = 0.0

        # Use string conversion that won't use scientific notation for typical inputs
        out = format(x, "f").rstrip("0").rstrip(".")
        if out == "-0":
            out = "0"

        self.setText(out)
        self.normalized.emit(out)

    # -------------------------
    # Convenience
    # -------------------------
    def value_or_none(self) -> Optional[float]:
        s = (self.text() or "").strip()
        if not s:
            return None
        s = s.replace(",", ".")
        try:
            return float(s)
        except Exception:
            return None