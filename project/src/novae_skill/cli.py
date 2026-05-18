from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Any
import json
import sys

from .renderer import render_package_files
from .runtime import (
    dispatch_action,
    discover_document_pages_action,
    extract_document_capabilities_action,
    classify_document_pages_action,
    generate_skill_files_action,
    normalize_capabilities_action,
    save_files_to_directory,
    validate_skill_package_action,
)
from .spec import build_default_file_tree, build_openapi_spec


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="docskill-factory",
        description="Generate a reusable skill package from a docs URL or GitHub repository URL.",
    )
    parser.add_argument("target_url", nargs="?", help="Documentation entry URL or GitHub repository URL")
    parser.add_argument("--url", dest="url", help="Alias for the target URL")
    parser.add_argument("--skill-name", dest="skill_name", help="Custom skill name")
    parser.add_argument("--project-name", dest="project_name", help="Custom project name")
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        help="Parent directory where the {skill-name} folder is written",
    )
    parser.add_argument("--site-name", dest="site_name", help="Optional site name to include in discovery output")
    parser.add_argument("--candidate-link", dest="candidate_links", action="append", default=[], help="Optional candidate link JSON or plain URL")
    parser.add_argument("--max-depth", dest="max_depth", type=int, default=2, help="Maximum crawl depth for docs discovery")
    parser.add_argument("--use-sitemap", dest="use_sitemap", action="store_true", help="Hint the discover step to consider sitemaps")
    parser.add_argument("--use-sidebar", dest="use_sidebar", action="store_true", help="Hint the discover step to consider sidebars")
    parser.add_argument("--use-next-prev", dest="use_next_prev", action="store_true", help="Hint the discover step to consider next/prev navigation")
    parser.add_argument("--spec", action="store_true", help="Print the OpenAPI-style workflow contract and exit")
    parser.add_argument("--file-tree", action="store_true", help="Print the default file tree and exit")
    parser.add_argument("--write-spec", metavar="PATH", help="Write the OpenAPI-style workflow contract to PATH")
    parser.add_argument("--json", action="store_true", help="Print the final package plan and validation report as JSON")
    return parser



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.write_spec:
        spec_path = Path(args.write_spec)
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(json.dumps(build_openapi_spec(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote workflow contract to {spec_path}")
        return 0

    if args.spec:
        print(json.dumps(build_openapi_spec(), indent=2, ensure_ascii=False))
        return 0

    if args.file_tree:
        for relative_path in build_default_file_tree():
            print(relative_path)
        return 0

    target_url = args.url or args.target_url
    if not target_url:
        parser.error("target_url is required unless --spec, --file-tree, or --write-spec is used")

    skill_name = args.skill_name or _derive_name_from_url(target_url)
    project_name = args.project_name or skill_name
    output_root = Path(args.output_dir) if args.output_dir else Path.cwd() / "build"
    skill_output_dir = output_root / skill_name

    print("[1/7] Discovering document pages")
    discovery_payload = {
        "entry_url": target_url,
        "site_name": args.site_name or "",
        "candidate_links": _parse_candidate_links(args.candidate_links),
        "navigation_hints": [],
        "exclusion_hints": [],
        "max_depth": args.max_depth,
        "use_sitemap": args.use_sitemap,
        "use_sidebar": args.use_sidebar,
        "use_next_prev": args.use_next_prev,
    }
    discovery_result = dispatch_action("discover_document_pages", discovery_payload)
    print(f"  discovered: {discovery_result['page_count']} page(s)")

    print("[2/7] Classifying discovered pages")
    classification_result = dispatch_action(
        "classify_document_pages",
        {
            "pages": discovery_result["discovered_pages"],
            "keep_kinds": ["tutorial", "guide", "example", "quickstart", "walkthrough", "how-to"],
            "exclude_kinds": ["marketing", "blog", "changelog", "release notes", "reference"],
            "prefer_code_samples": True,
            "prefer_api_dependencies": True,
        },
    )
    print(
        f"  kept: {classification_result['kept_count']} | excluded: {classification_result['excluded_count']}"
    )

    print("[3/7] Extracting capabilities")
    extracted_capabilities = _build_capability_model(classification_result["included_pages"], target_url)
    extract_result = dispatch_action(
        "extract_document_capabilities",
        {
            "pages": classification_result["included_pages"],
            "page_evidence": extracted_capabilities,
            "target_language": "python",
            "constraints": {
                "target_language": "python",
                "target_skill_format": "openapi",
                "allow_third_party_libs": True,
                "enable_local_cache": False,
                "enable_vector_index": False,
                "output_dir": str(output_root),
            },
        },
    )
    print(f"  capabilities: {extract_result['capability_count']}")

    print("[4/7] Normalizing capabilities")
    normalized_result = dispatch_action(
        "normalize_capabilities",
        {
            "capabilities": extract_result["capabilities"],
            "merge_strategy": "collapse_duplicates",
            "dedupe_keys": ["name"],
        },
    )
    print(f"  normalized: {normalized_result['capability_count']}")

    print("[5/7] Designing skill package")
    design_result = dispatch_action(
        "design_skill_package",
        {
            "entry_url": target_url,
            "project_name": project_name,
            "skill_name": skill_name,
            "constraints": {
                "target_language": "python",
                "target_skill_format": "openapi",
                "allow_third_party_libs": True,
                "enable_local_cache": False,
                "enable_vector_index": False,
                "output_dir": str(output_root),
            },
            "normalized_pages": classification_result["included_pages"],
            "capability_model": normalized_result["normalized_capabilities"],
        },
    )
    package_plan = design_result["package_plan"]
    print(f"  project: {package_plan['project_name']}")
    print(f"  skill: {package_plan['skill_name']}")

    print("[6/7] Generating skill files")
    generation_result = dispatch_action("generate_skill_files", {"package_plan": package_plan})
    files = generation_result["files"]
    print(f"  generated files: {len(files)}")

    print("[7/7] Saving files and validating package")
    saved_paths = save_files_to_directory(files, output_root, skill_name)
    validation_result = dispatch_action(
        "validate_skill_package",
        {"package_plan": package_plan, "files": files, "validation_mode": "standard"},
    )
    print(f"  saved to: {skill_output_dir.resolve()}")
    print(f"  saved paths: {len(saved_paths)}")
    print(f"  valid: {validation_result['valid']}")
    if validation_result["warnings"]:
        print("  warnings:")
        for warning in validation_result["warnings"]:
            print(f"    - {warning}")
    if validation_result["missing_files"]:
        print("  missing files:")
        for missing in validation_result["missing_files"]:
            print(f"    - {missing}")

    if args.json:
        print(
            json.dumps(
                {
                    "discovery": discovery_result,
                    "classification": classification_result,
                    "extract": extract_result,
                    "normalize": normalized_result,
                    "design": design_result,
                    "validation": validation_result,
                    "saved_paths": [str(path) for path in saved_paths],
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    return 0 if validation_result["valid"] else 1



def _parse_candidate_links(raw_links: list[str]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for value in raw_links:
        value = value.strip()
        if not value:
            continue
        if value.startswith("{"):
            try:
                candidate = json.loads(value)
                if isinstance(candidate, dict):
                    parsed.append(candidate)
                    continue
            except json.JSONDecodeError:
                pass
        parsed.append(
            {
                "title": _derive_name_from_url(value),
                "url": value,
                "kind": "documentation",
                "priority": "medium",
                "evidence": ["cli"],
                "reason": "Provided from command line",
            }
        )
    return parsed



def _derive_name_from_url(url: str) -> str:
    from urllib.parse import urlparse
    import re

    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return parsed.netloc.replace(".", "-") or "docskill"
    tail = parts[-1]
    tail = re.sub(r"[^a-zA-Z0-9]+", "-", tail).strip("-")
    return tail.lower() or parsed.netloc.replace(".", "-")



def _build_capability_model(pages: list[dict[str, Any]], target_url: str) -> list[dict[str, Any]]:
    if not pages:
        return [
            {
                "name": "discover_document_pages",
                "purpose": "Discover and normalize documentation pages.",
                "inputs": ["entry_url"],
                "outputs": ["page catalog"],
                "dependencies": ["navigation"],
                "risk_points": ["unknown links"],
                "evidence_pages": [target_url],
                "notes": ["fallback capability"],
            }
        ]

    capabilities: list[dict[str, Any]] = []
    for index, page in enumerate(pages):
        capabilities.append(
            {
                "name": _derive_name_from_url(page.get("url", target_url)) or f"capability_{index}",
                "purpose": page.get("reason") or f"Teach {page.get('title', 'documentation')}",
                "inputs": ["entry_url", "documentation pages"],
                "outputs": ["skill package artifact"],
                "dependencies": list(page.get("evidence", [])) or [page.get("kind", "documentation")],
                "risk_points": ["Documentation may be incomplete"],
                "evidence_pages": [page.get("url", target_url)],
                "notes": [page.get("title", "")],
            }
        )
    return capabilities


if __name__ == "__main__":
    raise SystemExit(main())
