from __future__ import annotations

from novae_skill.spec import (
    DEFAULT_DISCOVERY_HINTS,
    DEFAULT_FILE_TREE,
    SkillConstraint,
    build_openapi_spec,
    capability_names,
)


def test_default_discovery_hints_are_generic() -> None:
    assert "tutorial" in DEFAULT_DISCOVERY_HINTS
    assert "example" in DEFAULT_DISCOVERY_HINTS
    assert "how-to" in DEFAULT_DISCOVERY_HINTS


def test_openapi_has_core_actions() -> None:
    spec = build_openapi_spec()
    paths = spec["paths"]
    assert "/actions/discover_document_pages" in paths
    assert "/actions/classify_document_pages" in paths
    assert "/actions/design_skill_package" in paths
    assert "/actions/validate_skill_package" in paths


def test_capability_names_are_unique() -> None:
    names = capability_names()
    assert len(names) == len(set(names))
    assert "discover_document_pages" in names
    assert "generate_skill_files" in names


def test_default_file_tree_and_constraints_are_generic() -> None:
    assert "project/SKILL.md" in DEFAULT_FILE_TREE
    assert "project/schema/openapi.json" in DEFAULT_FILE_TREE
    constraint = SkillConstraint()
    assert constraint.target_language == "python"
    assert constraint.target_skill_format == "openapi"
