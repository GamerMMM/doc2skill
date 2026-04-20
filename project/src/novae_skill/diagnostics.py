from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnosis:
    category: str
    matched: str
    advice: str


KNOWN_FAILURE_PATTERNS = [
    ("missing files", Diagnosis("package-validation", "missing files", "Regenerate the package and include README, SKILL.md, schema, tests, and examples.")),
    ("no included pages", Diagnosis("page-selection", "no included pages", "Add tutorial-like pages to the included set before generating the skill package.")),
    ("no capability model", Diagnosis("capability-extraction", "no capability model", "Extract and normalize capabilities from the selected pages first.")),
    ("unsupported", Diagnosis("format", "unsupported", "Switch to a supported target language or skill format before generating files.")),
    ("python version", Diagnosis("environment", "python version", "Lower the package's minimum Python version or use a matching virtual environment.")),
]


def diagnose_error(message: str) -> Diagnosis:
    lowered = message.lower()
    for needle, diagnosis in KNOWN_FAILURE_PATTERNS:
        if needle in lowered:
            return diagnosis
    return Diagnosis("unknown", message[:120], "Check discovery coverage, capability extraction, and package validation inputs.")