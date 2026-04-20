from __future__ import annotations

from novae_skill.runtime import dispatch_action


def main() -> None:
    plan = dispatch_action(
        "design_skill_package",
        {
            "entry_url": "https://example.com/docs",
            "project_name": "docskill-factory-demo",
            "skill_name": "docskill-factory-demo",
            "normalized_pages": [],
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
    print(report["valid"])
    print(len(files["files"]))


if __name__ == "__main__":
    main()
