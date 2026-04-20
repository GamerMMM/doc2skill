from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .spec import (
    CapabilityRecord,
    PageRecord,
    SkillConstraint,
    SkillPackagePlan,
    build_default_file_tree,
    normalize_capability_record,
    normalize_page_record,
)


def dispatch_action(action_name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    handlers = {
        "discover_document_pages": discover_document_pages_action,
        "classify_document_pages": classify_document_pages_action,
        "extract_document_capabilities": extract_document_capabilities_action,
        "normalize_capabilities": normalize_capabilities_action,
        "design_skill_package": design_skill_package_action,
        "generate_skill_files": generate_skill_files_action,
        "validate_skill_package": validate_skill_package_action,
    }

    if action_name not in handlers:
        raise KeyError("Unknown action: %s" % action_name)

    return handlers[action_name]({} if payload is None else dict(payload))


def discover_document_pages_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    entry_url = str(payload.get("entry_url", ""))
    candidate_links = [normalize_page_record(item) for item in payload.get("candidate_links", [])]
    navigation_hints = list(payload.get("navigation_hints", []))
    exclusion_hints = list(payload.get("exclusion_hints", []))

    discovered = [asdict(page) for page in candidate_links]
    return {
        "entry_url": entry_url,
        "navigation_hints": navigation_hints,
        "exclusion_hints": exclusion_hints,
        "discovered_pages": discovered,
        "page_count": len(discovered),
    }


def classify_document_pages_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    pages = [normalize_page_record(item) for item in payload.get("pages", [])]
    keep_kinds = set(payload.get("keep_kinds", ["tutorial", "guide", "example", "quickstart", "walkthrough", "how-to"]))
    exclude_kinds = set(payload.get("exclude_kinds", ["marketing", "blog", "changelog", "release notes", "reference"]))

    included: List[PageRecord] = []
    excluded: List[PageRecord] = []
    for page in pages:
        if page.kind in exclude_kinds:
            excluded.append(page)
        elif page.kind in keep_kinds:
            included.append(page)
        else:
            excluded.append(page)

    return {
        "included_pages": [asdict(page) for page in included],
        "excluded_pages": [asdict(page) for page in excluded],
        "kept_count": len(included),
        "excluded_count": len(excluded),
    }


def extract_document_capabilities_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    pages = [normalize_page_record(item) for item in payload.get("pages", [])]
    page_evidence = payload.get("page_evidence", [])
    target_language = str(payload.get("target_language", "python"))
    constraints = payload.get("constraints", {})

    capabilities = []
    for entry in page_evidence:
        capability = normalize_capability_record(entry)
        capabilities.append(asdict(capability))

    return {
        "pages": [asdict(page) for page in pages],
        "capabilities": capabilities,
        "target_language": target_language,
        "constraints": constraints,
    }


def normalize_capabilities_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    capabilities = [normalize_capability_record(item) for item in payload.get("capabilities", [])]
    merge_strategy = str(payload.get("merge_strategy", "collapse_duplicates"))
    dedupe_keys = list(payload.get("dedupe_keys", ["name"]))

    merged: Dict[str, CapabilityRecord] = {}
    for capability in capabilities:
        if capability.name not in merged:
            merged[capability.name] = capability
            continue

        current = merged[capability.name]
        merged[capability.name] = CapabilityRecord(
            name=current.name,
            purpose=current.purpose or capability.purpose,
            inputs=sorted(set(current.inputs + capability.inputs)),
            outputs=sorted(set(current.outputs + capability.outputs)),
            dependencies=sorted(set(current.dependencies + capability.dependencies)),
            risk_points=sorted(set(current.risk_points + capability.risk_points)),
            evidence_pages=sorted(set(current.evidence_pages + capability.evidence_pages)),
            notes=sorted(set(current.notes + capability.notes)),
        )

    normalized = [asdict(item) for item in merged.values()]
    return {
        "merge_strategy": merge_strategy,
        "dedupe_keys": dedupe_keys,
        "normalized_capabilities": normalized,
    }


def design_skill_package_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    entry_url = str(payload.get("entry_url", ""))
    constraints_data = dict(payload.get("constraints", {}))
    constraints = SkillConstraint(**constraints_data) if constraints_data else SkillConstraint()
    pages = [normalize_page_record(item) for item in payload.get("normalized_pages", payload.get("pages", []))]
    capabilities = [normalize_capability_record(item) for item in payload.get("capability_model", [])]

    project_name = str(payload.get("project_name", "project"))
    skill_name = str(payload.get("skill_name", "document-link-skill-factory"))
    file_tree = list(payload.get("file_tree", build_default_file_tree()))

    install_notes = [
        "Create an isolated Python environment.",
        "Install the generated package in editable mode.",
        "Keep the OpenAPI schema and notebook tests in sync with the extracted docs.",
    ]
    validation_checks = [
        "At least one tutorial or guide page is included.",
        "No unsupported API or parameters were invented.",
        "The package has README, SKILL.md, schema, tests, and examples.",
    ]

    plan = SkillPackagePlan(
        project_name=project_name,
        skill_name=skill_name,
        entry_url=entry_url,
        constraints=constraints,
        discovered_pages=pages,
        included_pages=pages,
        excluded_pages=[],
        capability_model=capabilities,
        file_tree=file_tree,
        install_notes=install_notes,
        validation_checks=validation_checks,
    )

    return {"package_plan": asdict(plan)}


def generate_skill_files_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    package_plan = payload.get("package_plan", {})
    files = _render_files(package_plan)
    return {"files": files}


def validate_skill_package_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    package_plan = payload.get("package_plan", {})
    files = dict(payload.get("files", {}))
    required = [
        "project/SKILL.md",
        "project/README.md",
        "project/pyproject.toml",
        "project/schema/openapi.json",
        "project/tests/test_spec.py",
        "project/tests/test_runtime.py",
        "project/tests/notebook_tests.ipynb",
    ]

    missing = [path for path in required if path not in files]
    warnings = []
    if not package_plan.get("included_pages"):
        warnings.append("No included pages were provided; the skill package may be under-specified.")
    if not package_plan.get("capability_model"):
        warnings.append("No capability model was provided; extraction likely needs another pass.")

    return {
        "valid": not missing,
        "missing_files": missing,
        "warnings": warnings,
    }


def _render_files(package_plan: Dict[str, Any]) -> Dict[str, str]:
    project_name = str(package_plan.get("project_name", "project"))
    skill_name = str(package_plan.get("skill_name", "document-link-skill-factory"))
    entry_url = str(package_plan.get("entry_url", ""))
    capabilities = package_plan.get("capability_model", [])
    file_tree = package_plan.get("file_tree", build_default_file_tree())

    file_map = {
        "project/SKILL.md": _render_skill_md(skill_name, entry_url, capabilities),
        "project/README.md": _render_readme(project_name, skill_name),
        "project/pyproject.toml": _render_pyproject(project_name),
        "project/.env.example": _render_env_example(),
        "project/schema/openapi.json": json.dumps({"note": "generated by validate_skill_package_action"}, indent=2),
        "project/src/docskill_factory/__init__.py": "from .spec import build_openapi_spec\n",
        "project/src/docskill_factory/spec.py": "from __future__ import annotations\n\n",
        "project/src/docskill_factory/runtime.py": "from __future__ import annotations\n\n",
        "project/src/docskill_factory/renderer.py": _render_renderer_stub(),
        "project/tests/test_spec.py": _render_test_spec(),
        "project/tests/test_runtime.py": _render_test_runtime(),
        "project/tests/notebook_tests.ipynb": _render_notebook_stub(),
        "project/examples/discover_and_generate.py": _render_example_discover_and_generate(),
        "project/examples/package_validation.py": _render_example_package_validation(),
    }

    return {path: file_map[path] for path in file_tree if path in file_map}


def _render_skill_md(skill_name: str, entry_url: str, capabilities: List[Dict[str, Any]]) -> str:
    lines = [
        "---",
        f"name: {skill_name}",
        "description: Use when converting official documentation into a reusable skill package.",
        "---",
        "",
        "# Document Link Skill Factory",
        "",
        "## Overview",
        "This generated skill is driven by a discovered documentation entry URL and a capability model.",
        "",
        "## Entry URL",
        entry_url or "unknown",
        "",
        "## Capabilities",
    ]
    for capability in capabilities:
        lines.append(f"- {capability.get('name', 'unknown')}: {capability.get('purpose', '')}")
    return "\n".join(lines) + "\n"


def _render_readme(project_name: str, skill_name: str) -> str:
    return "\n".join([
        f"# {project_name}",
        "",
        "Reusable workflow for converting a documentation entry URL into a skill package.",
        "",
        "## Installation",
        "```bash",
        "pip install -e .",
        "```",
        "",
        "## Testing",
        "Run `pytest` and execute `tests/notebook_tests.ipynb`.",
        "",
        f"## Skill",
        f"The generated skill is named {skill_name}.",
        "",
    ])


def _render_pyproject(project_name: str) -> str:
    return "\n".join([
        "[build-system]",
        'requires = ["setuptools>=68", "wheel"]',
        'build-backend = "setuptools.build_meta"',
        "",
        "[project]",
        f'name = "{project_name}"',
        'version = "0.1.0"',
        'description = "Reusable workflow for turning documentation links into skills"',
        'requires-python = ">=3.9"',
        'dependencies = []',
        "",
    ])


def _render_env_example() -> str:
    return "\n".join([
        "DOC_URL=",
        "TARGET_LANGUAGE=python",
        "TARGET_SKILL_FORMAT=openapi",
        "ALLOW_THIRD_PARTY_LIBS=1",
        "CACHE_DIR=.cache/docskill",
        "OUTPUT_DIR=./project",
        "",
    ])


def _render_renderer_stub() -> str:
    return "from __future__ import annotations\n\n"


def _render_test_spec() -> str:
    return "from __future__ import annotations\n\nfrom docskill_factory.spec import build_openapi_spec, capability_names\n\n\ndef test_openapi_has_core_workflow_actions() -> None:\n    spec = build_openapi_spec()\n    assert '/actions/discover_document_pages' in spec['paths']\n    assert '/actions/design_skill_package' in spec['paths']\n\n\ndef test_capability_names_are_generic() -> None:\n    names = capability_names()\n    assert 'discover_document_pages' in names\n    assert 'validate_skill_package' in names\n"


def _render_test_runtime() -> str:
    return "from __future__ import annotations\n\nfrom docskill_factory.runtime import dispatch_action\n\n\ndef test_dispatch_actions_are_pure_transforms() -> None:\n    pages = [{'title': 'Guide', 'url': 'https://example.com/guide', 'kind': 'guide', 'priority': 'high', 'evidence': ['nav'], 'reason': 'official'}]\n    discovered = dispatch_action('discover_document_pages', {'entry_url': 'https://example.com', 'candidate_links': pages})\n    assert discovered['page_count'] == 1\n    classified = dispatch_action('classify_document_pages', {'pages': pages})\n    assert classified['kept_count'] == 1\n"


def _render_notebook_stub() -> str:
    return json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}, indent=2)


def _render_example_discover_and_generate() -> str:
    return "from docskill_factory.runtime import dispatch_action\n\nentry_url = 'https://example.com/docs/'\npages = [\n    {'title': 'Quickstart', 'url': 'https://example.com/docs/quickstart/', 'kind': 'quickstart', 'priority': 'high', 'evidence': ['sidebar'], 'reason': 'contains setup steps'},\n]\nprint(dispatch_action('discover_document_pages', {'entry_url': entry_url, 'candidate_links': pages}))\n"


def _render_example_package_validation() -> str:
    return "from docskill_factory.runtime import dispatch_action\n\nplan = dispatch_action('design_skill_package', {'entry_url': 'https://example.com/docs', 'normalized_pages': [], 'capability_model': []})\nfiles = dispatch_action('generate_skill_files', {'package_plan': plan['package_plan']})\nprint(dispatch_action('validate_skill_package', {'package_plan': plan['package_plan'], 'files': files['files']}))\n"