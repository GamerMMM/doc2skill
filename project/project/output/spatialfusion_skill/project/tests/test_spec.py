from __future__ import annotations

from docskill_factory.spec import build_openapi_spec, capability_names


def test_openapi_has_core_workflow_actions() -> None:
    spec = build_openapi_spec()
    assert '/actions/discover_document_pages' in spec['paths']
    assert '/actions/design_skill_package' in spec['paths']


def test_capability_names_are_generic() -> None:
    names = capability_names()
    assert 'discover_document_pages' in names
    assert 'validate_skill_package' in names
