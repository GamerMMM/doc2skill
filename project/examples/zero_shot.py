from __future__ import annotations

from novae_skill.runtime import dispatch_action


def main() -> None:
    pages = [
        {
            "title": "Quickstart",
            "url": "https://example.com/docs/quickstart/",
            "kind": "quickstart",
            "priority": "high",
            "evidence": ["sidebar"],
            "reason": "official entry guide",
        }
    ]
    plan = dispatch_action(
        "design_skill_package",
        {
            "entry_url": "https://example.com/docs/",
            "project_name": "docskill-factory-demo",
            "skill_name": "docskill-factory-demo",
            "normalized_pages": pages,
            "capability_model": [],
        },
    )
    print(plan["package_plan"]["skill_name"])
    print(plan["package_plan"]["file_tree"][0])


if __name__ == "__main__":
    main()
