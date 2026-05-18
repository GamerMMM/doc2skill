from __future__ import annotations

import docskill_factory.spec as spec_module


def test_openapi_has_core_workflow_actions() -> None:
    build_openapi_spec = getattr(spec_module, 'build_openapi_spec', None)
    assert callable(build_openapi_spec), 'docskill_factory.spec.build_openapi_spec is missing'
    spec = build_openapi_spec()
    assert '/actions/discover_document_pages' in spec['paths']
    assert '/actions/design_skill_package' in spec['paths']


def test_capability_names_are_generic() -> None:
    capability_names = getattr(spec_module, 'capability_names', None)
    assert callable(capability_names), 'docskill_factory.spec.capability_names is missing'
    names = capability_names()
    assert 'discover_document_pages' in names
    assert 'validate_skill_package' in names
