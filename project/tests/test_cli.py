from __future__ import annotations

from pathlib import Path

from novae_skill import cli


def test_cli_writes_package_to_output_dir(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []
    output_roots: list[str] = []

    def fake_dispatch_action(action_name, payload=None):
        calls.append(action_name)
        payload = payload or {}
        if action_name == "discover_document_pages":
            return {
                "entry_url": payload["entry_url"],
                "page_count": 1,
                "discovered_pages": [
                    {
                        "title": "Quickstart",
                        "url": "https://example.com/docs/quickstart/",
                        "kind": "quickstart",
                        "priority": "high",
                        "evidence": ["sidebar"],
                        "reason": "official tutorial",
                    }
                ],
                "discovery_mode": "web",
                "site_name": "Example Docs",
            }
        if action_name == "classify_document_pages":
            return {
                "kept_count": 1,
                "excluded_count": 0,
                "included_pages": payload["pages"],
                "excluded_pages": [],
                "priority_scores": [{"title": "Quickstart", "url": "https://example.com/docs/quickstart/", "score": 3}],
            }
        if action_name == "extract_document_capabilities":
            return {
                "capabilities": [
                    {
                        "name": "quickstart",
                        "purpose": "Show the user how to start.",
                        "inputs": ["entry_url"],
                        "outputs": ["skill package artifact"],
                        "dependencies": ["docs"],
                        "risk_points": ["missing tutorial coverage"],
                        "evidence_pages": ["https://example.com/docs/quickstart/"],
                        "notes": ["derived"],
                    }
                ],
                "capability_count": 1,
                "target_language": "python",
                "constraints": payload.get("constraints", {}),
            }
        if action_name == "normalize_capabilities":
            return {
                "normalized_capabilities": payload["capabilities"],
                "capability_count": len(payload["capabilities"]),
                "merge_strategy": payload.get("merge_strategy", "collapse_duplicates"),
                "dedupe_keys": payload.get("dedupe_keys", ["name"]),
            }
        if action_name == "design_skill_package":
            output_roots.append(str(payload["constraints"]["output_dir"]))
            return {
                "package_plan": {
                    "project_name": payload["project_name"],
                    "skill_name": payload["skill_name"],
                    "entry_url": payload["entry_url"],
                    "file_tree": [
                        "project/SKILL.md",
                        "project/README.md",
                        "project/pyproject.toml",
                    ],
                    "capability_model": payload["capability_model"],
                    "included_pages": payload["normalized_pages"],
                    "constraints": payload["constraints"],
                    "install_instructions": ["pip install -e ."],
                    "validation_checks": ["project/SKILL.md exists"],
                }
            }
        if action_name == "generate_skill_files":
            return {"files": {
                "project/SKILL.md": "# demo\n",
                "project/README.md": "# demo\n",
                "project/pyproject.toml": "[project]\nname='demo'\n",
            }, "package_plan": payload["package_plan"]}
        if action_name == "validate_skill_package":
            return {
                "valid": True,
                "missing_files": [],
                "extra_files": [],
                "warnings": [],
                "expected_files": payload["package_plan"]["file_tree"],
                "present_files": list(payload["files"].keys()),
                "validation_mode": payload.get("validation_mode", "standard"),
            }
        raise AssertionError(f"unexpected action: {action_name}")

    monkeypatch.setattr(cli, "dispatch_action", fake_dispatch_action)

    exit_code = cli.main([
        "https://example.com/docs/",
        "--skill-name",
        "demo-skill",
        "--output-dir",
        str(tmp_path),
    ])

    assert exit_code == 0
    assert output_roots == [str(tmp_path)]
    assert (tmp_path / "demo-skill" / "project" / "SKILL.md").exists()
    assert (tmp_path / "demo-skill" / "project" / "README.md").exists()
    assert (tmp_path / "demo-skill" / "project" / "pyproject.toml").exists()
    assert calls[:3] == ["discover_document_pages", "classify_document_pages", "extract_document_capabilities"]
