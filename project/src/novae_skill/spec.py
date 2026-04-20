from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Union


@dataclass(frozen=True)
class PageRecord:
    title: str
    url: str
    kind: str
    priority: str
    evidence: List[str]
    reason: str


@dataclass(frozen=True)
class CapabilityRecord:
    name: str
    purpose: str
    inputs: List[str]
    outputs: List[str]
    dependencies: List[str]
    risk_points: List[str]
    evidence_pages: List[str]
    notes: List[str]


@dataclass(frozen=True)
class SkillConstraint:
    target_language: str = "python"
    target_skill_format: str = "openapi"
    allow_third_party_libs: bool = True
    enable_local_cache: bool = False
    enable_vector_index: bool = False
    output_dir: str = "./project"


@dataclass(frozen=True)
class SkillPackagePlan:
    project_name: str
    skill_name: str
    entry_url: str
    constraints: SkillConstraint
    discovered_pages: List[PageRecord]
    included_pages: List[PageRecord]
    excluded_pages: List[PageRecord]
    capability_model: List[CapabilityRecord]
    file_tree: List[str]
    install_notes: List[str]
    validation_checks: List[str]


DEFAULT_DISCOVERY_HINTS = ["tutorial", "guide", "example", "quickstart", "walkthrough", "how-to"]
DEFAULT_EXCLUSION_HINTS = ["marketing", "blog", "changelog", "release notes", "reference"]
DEFAULT_INCLUDE_KINDS = ["tutorial", "guide", "example", "quickstart", "walkthrough", "how-to"]
DEFAULT_EXCLUDE_KINDS = ["marketing", "blog", "changelog", "release notes", "reference"]

DEFAULT_FILE_TREE = [
    "project/SKILL.md",
    "project/README.md",
    "project/pyproject.toml",
    "project/.env.example",
    "project/schema/openapi.json",
    "project/src/docskill_factory/__init__.py",
    "project/src/docskill_factory/spec.py",
    "project/src/docskill_factory/runtime.py",
    "project/src/docskill_factory/renderer.py",
    "project/tests/test_spec.py",
    "project/tests/test_runtime.py",
    "project/tests/notebook_tests.ipynb",
    "project/examples/discover_and_generate.py",
    "project/examples/package_validation.py",
]

CORE_ACTIONS = [
    {
        "name": "discover_document_pages",
        "purpose": "Normalize and score candidate pages discovered from a documentation entry URL.",
        "inputs": ["entry_url", "site_name", "candidate_links", "navigation_hints", "exclusion_hints", "max_depth", "use_sitemap", "use_sidebar", "use_next_prev"],
        "outputs": ["normalized page catalog"],
        "dependencies": ["site navigation, sidebar, sitemap, next/prev links"],
        "risk_points": ["Do not treat the entry page as the whole docs site.", "Record unknown links as unknown rather than guessing."],
        "handler": "discover_document_pages_action",
    },
    {
        "name": "classify_document_pages",
        "purpose": "Split discovered pages into tutorial-like pages and lower-priority pages.",
        "inputs": ["pages", "keep_kinds", "exclude_kinds", "prefer_code_samples", "prefer_api_dependencies"],
        "outputs": ["included pages", "excluded pages", "priority scores"],
        "dependencies": ["page titles, headings, sidebars, code fences, linked dependencies"],
        "risk_points": ["Marketing pages and changelogs should be demoted.", "Pure API reference should be retained only when tutorials depend on it."],
        "handler": "classify_document_pages_action",
    },
    {
        "name": "extract_document_capabilities",
        "purpose": "Turn page evidence into a capability model with inputs, outputs, dependencies, risks, and notes.",
        "inputs": ["pages", "page_evidence", "constraints", "target_language"],
        "outputs": ["capability records"],
        "dependencies": ["code blocks, steps, parameters, return values, errors, prerequisites"],
        "risk_points": ["Capture assumptions explicitly when documentation is incomplete.", "Merge repeated workflows rather than duplicating them."],
        "handler": "extract_document_capabilities_action",
    },
    {
        "name": "normalize_capabilities",
        "purpose": "Merge duplicate capabilities and produce a unified abstraction layer.",
        "inputs": ["capabilities", "merge_strategy", "dedupe_keys"],
        "outputs": ["normalized capability model"],
        "dependencies": ["repeated initialization, authentication, client creation, and common parameters"],
        "risk_points": ["Do not overfit to one example page.", "Keep separate actions when page workflows differ materially."],
        "handler": "normalize_capabilities_action",
    },
    {
        "name": "design_skill_package",
        "purpose": "Design the concrete skill package, schema, file tree, and install instructions.",
        "inputs": ["entry_url", "constraints", "capability_model", "normalized_pages"],
        "outputs": ["skill package plan"],
        "dependencies": ["OpenAPI-style schema, README, SKILL.md, tests, examples"],
        "risk_points": ["Keep the package installable and testable.", "Expose assumptions and unknowns in the plan."],
        "handler": "design_skill_package_action",
    },
    {
        "name": "generate_skill_files",
        "purpose": "Render file contents for the planned skill package.",
        "inputs": ["package_plan", "emit_json_schema", "emit_notebook_tests", "emit_examples"],
        "outputs": ["file map"],
        "dependencies": ["template rendering, code stubs, test templates"],
        "risk_points": ["Generated code should not hardcode undocumented APIs.", "Files should reflect the selected target language and format."],
        "handler": "generate_skill_files_action",
    },
    {
        "name": "validate_skill_package",
        "purpose": "Validate that the generated skill package is installable, testable, and aligned with the extracted docs.",
        "inputs": ["package_plan", "files", "validation_mode"],
        "outputs": ["validation report"],
        "dependencies": ["file presence checks, schema checks, notebook checks"],
        "risk_points": ["Call out missing tutorial coverage and unresolved assumptions.", "Separate hard failures from soft warnings."],
        "handler": "validate_skill_package_action",
    },
]


def capability_names() -> List[str]:
    return [item["name"] for item in CORE_ACTIONS]


def build_default_file_tree() -> List[str]:
    return list(DEFAULT_FILE_TREE)


def normalize_page_record(record: Dict[str, Any]) -> PageRecord:
    return PageRecord(
        title=str(record.get("title", "")),
        url=str(record.get("url", "")),
        kind=str(record.get("kind", "unknown")),
        priority=str(record.get("priority", "medium")),
        evidence=list(record.get("evidence", [])),
        reason=str(record.get("reason", "")),
    )


def normalize_capability_record(record: Dict[str, Any]) -> CapabilityRecord:
    return CapabilityRecord(
        name=str(record.get("name", "")),
        purpose=str(record.get("purpose", "")),
        inputs=list(record.get("inputs", [])),
        outputs=list(record.get("outputs", [])),
        dependencies=list(record.get("dependencies", [])),
        risk_points=list(record.get("risk_points", [])),
        evidence_pages=list(record.get("evidence_pages", [])),
        notes=list(record.get("notes", [])),
    )


def build_openapi_spec() -> Dict[str, Any]:
    paths: Dict[str, Any] = {}
    for action in CORE_ACTIONS:
        paths[f"/actions/{action['name']}"] = {
            "post": {
                "operationId": action["name"],
                "summary": action["purpose"],
                "description": "\n".join(action["risk_points"]),
                "tags": ["DocumentSkillFactory"],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "responses": {
                    "200": {
                        "description": "Successful workflow step.",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
                "x-inputs": action["inputs"],
                "x-outputs": action["outputs"],
                "x-dependencies": action["dependencies"],
                "x-risk-points": action["risk_points"],
                "x-handler": action["handler"],
            }
        }

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Document Link Skill Factory",
            "version": "0.1.0",
            "description": "OpenAPI-style workflow contract for turning a documentation entry URL into a reusable skill package.",
        },
        "paths": paths,
        "components": {
            "schemas": {
                "PageRecord": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "kind": {"type": "string"},
                        "priority": {"type": "string"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                        "reason": {"type": "string"},
                    },
                },
                "CapabilityRecord": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "purpose": {"type": "string"},
                    },
                },
                "SkillConstraint": {
                    "type": "object",
                    "properties": {
                        "target_language": {"type": "string"},
                        "target_skill_format": {"type": "string"},
                        "allow_third_party_libs": {"type": "boolean"},
                        "enable_local_cache": {"type": "boolean"},
                        "enable_vector_index": {"type": "boolean"},
                        "output_dir": {"type": "string"},
                    },
                },
                "SkillPackagePlan": {
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string"},
                        "skill_name": {"type": "string"},
                        "entry_url": {"type": "string"},
                        "file_tree": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        },
        "x-default-discovery-hints": DEFAULT_DISCOVERY_HINTS,
        "x-default-exclusion-hints": DEFAULT_EXCLUSION_HINTS,
        "x-default-include-kinds": DEFAULT_INCLUDE_KINDS,
        "x-default-exclude-kinds": DEFAULT_EXCLUDE_KINDS,
        "x-default-file-tree": DEFAULT_FILE_TREE,
        "x-core-actions": CORE_ACTIONS,
    }


def dump_openapi_spec(path: Union[str, Path]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_openapi_spec(), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def summarize_package_plan(plan: SkillPackagePlan) -> Dict[str, Any]:
    return {
        "project_name": plan.project_name,
        "skill_name": plan.skill_name,
        "entry_url": plan.entry_url,
        "constraints": asdict(plan.constraints),
        "discovered_pages": [asdict(page) for page in plan.discovered_pages],
        "included_pages": [asdict(page) for page in plan.included_pages],
        "excluded_pages": [asdict(page) for page in plan.excluded_pages],
        "capability_model": [asdict(capability) for capability in plan.capability_model],
        "file_tree": plan.file_tree,
        "install_notes": plan.install_notes,
        "validation_checks": plan.validation_checks,
    }