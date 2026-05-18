from __future__ import annotations

from novae_skill.runtime import dispatch_action
from novae_skill.renderer import render_package_files


def test_discover_and_classify_with_seed_links() -> None:
    discovery = dispatch_action(
        "discover_document_pages",
        {
            "entry_url": "https://example.com/docs/",
            "candidate_links": [
                {
                    "title": "Getting Started Tutorial",
                    "url": "https://example.com/docs/tutorial/",
                    "kind": "tutorial",
                    "priority": "high",
                    "evidence": ["sidebar"],
                    "reason": "official tutorial",
                },
                {
                    "title": "Library Reference",
                    "url": "https://example.com/docs/api/",
                    "kind": "reference",
                    "priority": "medium",
                    "evidence": ["sidebar"],
                    "reason": "api docs",
                },
            ],
        },
    )

    assert discovery["page_count"] >= 2
    assert any(page["kind"] == "tutorial" for page in discovery["discovered_pages"])

    classification = dispatch_action(
        "classify_document_pages",
        {
            "pages": discovery["discovered_pages"],
            "keep_kinds": ["tutorial", "guide", "example", "quickstart"],
            "exclude_kinds": ["reference", "blog", "changelog"],
        },
    )

    assert classification["kept_count"] >= 1
    assert classification["excluded_count"] >= 1
    assert any(page["kind"] == "tutorial" for page in classification["included_pages"])


def test_full_pipeline_generates_valid_package() -> None:
    pages = [
        {
            "title": "Quickstart",
            "url": "https://example.com/docs/quickstart/",
            "kind": "quickstart",
            "priority": "high",
            "evidence": ["sidebar"],
            "reason": "entry guide",
        }
    ]
    capabilities = [
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
    ]

    design = dispatch_action(
        "design_skill_package",
        {
            "entry_url": "https://example.com/docs",
            "project_name": "docskill-factory-demo",
            "skill_name": "docskill-factory-demo",
            "normalized_pages": pages,
            "capability_model": capabilities,
        },
    )
    files = dispatch_action("generate_skill_files", {"package_plan": design["package_plan"]})
    report = dispatch_action(
        "validate_skill_package",
        {"package_plan": design["package_plan"], "files": files["files"]},
    )

    assert report["valid"] is True
    assert "project/SKILL.md" in files["files"]
    assert "project/schema/openapi.json" in files["files"]
    assert len(files["files"]) >= 10


def test_generated_skill_markdown_is_not_indented() -> None:
    files = render_package_files(
        {
            "skill_name": "demo-skill",
            "project_name": "demo-skill",
            "entry_url": "https://example.com/docs/",
            "capability_model": [
                {
                    "name": "quickstart",
                    "purpose": "Show users how to start.",
                }
            ],
            "included_pages": [
                {
                    "title": "Quickstart",
                    "kind": "tutorial",
                }
            ],
            "file_tree": ["project/SKILL.md"],
            "constraints": {},
        }
    )

    skill_md = files["project/SKILL.md"]
    lines = skill_md.splitlines()

    assert lines[0] == "---"
    assert lines[1] == "name: demo-skill"
    assert lines[5] == "# Document Link Skill Factory"
    assert "## Included Pages" in lines
    assert "- Quickstart (tutorial)" in lines
    assert "## Capabilities" in lines
    assert "- quickstart: Show users how to start." in lines
