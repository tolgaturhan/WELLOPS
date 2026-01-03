from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(slots=True)
class ValidationResult:
    """
    Locked project standard for rule outputs.

    - ok: Blocking status. If False, the caller must not proceed.
    - errors: Form-level blocking messages (English only).
    - field_errors: Field-specific blocking messages (English only).
    - warnings: Non-blocking messages (English only).
    """
    ok: bool = True
    errors: List[str] = field(default_factory=list)
    field_errors: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        if message:
            self.errors.append(message)
            self.ok = False

    def add_field_error(self, field_name: str, message: str) -> None:
        if field_name and message:
            self.field_errors[field_name] = message
            self.ok = False

    def add_warning(self, message: str) -> None:
        if message:
            self.warnings.append(message)

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """
        Merge another ValidationResult into this one.
        - ok becomes False if either is False
        - errors/warnings are appended
        - field_errors are merged (other wins on same key)
        """
        if not other.ok:
            self.ok = False

        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.field_errors.update(other.field_errors)
        return self


def ok_result() -> ValidationResult:
    return ValidationResult(ok=True)


def error_result(message: str, *, field_name: Optional[str] = None) -> ValidationResult:
    r = ValidationResult(ok=False)
    if field_name:
        r.add_field_error(field_name, message)
    else:
        r.add_error(message)
    return r


# Optional: re-export commonly used rule entry points (we will add these next steps)
from .step1_rules import validate_step1
from .step2_rules import validate_step2
# from .step3_rules import validate_step3
# from .export_rules import validate_export