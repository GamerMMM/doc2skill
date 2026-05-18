from __future__ import annotations

from typing import Any, Mapping


def summarize_validation_report(report: Mapping[str, Any]) -> str:
    valid = bool(report.get("valid"))
    missing_files = list(report.get("missing_files", []))
    warnings = list(report.get("warnings", []))
    if valid:
        return "Skill package validation passed."
    details = []
    if missing_files:
        details.append(f"missing_files={len(missing_files)}")
    if warnings:
        details.append(f"warnings={len(warnings)}")
    if not details:
        details.append("validation failed")
    return "Skill package validation failed: " + ", ".join(details)
