from __future__ import annotations

from novae_skill.runtime import dispatch_action


def main() -> None:
    pages = [
        {
            "title": "Tutorial",
            "url": "https://example.com/docs/tutorial/",
            "kind": "tutorial",
            "priority": "high",
            "evidence": ["nav"],
            "reason": "step-by-step documentation",
        },
        {
            "title": "API reference",
            "url": "https://example.com/docs/api/",
            "kind": "reference",
            "priority": "medium",
            "evidence": ["sidebar"],
            "reason": "depends on tutorial pages",
        },
    ]
    classified = dispatch_action("classify_document_pages", {"pages": pages})
    print(classified["kept_count"])
    print(classified["excluded_count"])


if __name__ == "__main__":
    main()
