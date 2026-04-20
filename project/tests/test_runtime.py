from __future__ import annotations

from novae_skill.diagnostics import diagnose_error
from novae_skill.runtime import dispatch_action


def test_dispatch_discovery_and_classification() -> None:
    pages = [
        {
            "title": "Quickstart",
            "url": "https://example.com/docs/quickstart/",
            "kind": "quickstart",
            "priority": "high",
            "evidence": ["sidebar"],
            "reason": "entry guide",
        },
        {
            "title": "Release notes",
            "url": "https://example.com/docs/releases/",
            "kind": "changelog",
            "priority": "low",
            "evidence": ["footer"],
            "reason": "release log",
        },
    ]

    discovered = dispatch_action("discover_document_pages", {"entry_url": "https://example.com/docs", "candidate_links": pages})
    assert discovered["page_count"] == 2

    classified = dispatch_action("classify_document_pages", {"pages": pages})
    assert classified["kept_count"] == 1
    assert classified["excluded_count"] == 1


def test_design_generate_validate_flow() -> None:
    plan = dispatch_action(
        "design_skill_package",
        {
            "entry_url": "https://example.com/docs",
            "project_name": "docskill-factory-demo",
            "skill_name": "docskill-factory-demo",
            "normalized_pages": [
                {
                    "title": "Quickstart",
                    "url": "https://example.com/docs/quickstart/",
                    "kind": "quickstart",
                    "priority": "high",
                    "evidence": ["sidebar"],
                    "reason": "entry guide",
                }
            ],
            "capability_model": [
                {
                    "name": "discover_document_pages",
                    "purpose": "Normalize docs pages.",
                    "inputs": ["entry_url"],
                    "outputs": ["page catalog"],
                    "dependencies": ["navigation"],
                    "risk_points": ["unknown links"],
                    "evidence_pages": ["https://example.com/docs/quickstart/"],
                    "notes": ["generic"],
                }
            ],
        },
    )
    files = dispatch_action("generate_skill_files", {"package_plan": plan["package_plan"]})
    report = dispatch_action("validate_skill_package", {"package_plan": plan["package_plan"], "files": files["files"]})

    assert plan["package_plan"]["skill_name"] == "docskill-factory-demo"
    assert "project/SKILL.md" in files["files"]
    assert report["valid"] is True
    assert report["missing_files"] == []


def test_diagnose_error_maps_known_patterns() -> None:
    diagnosis = diagnose_error("missing files in generated package")
    assert diagnosis.category == "package-validation"
    assert "README" in diagnosis.advice
