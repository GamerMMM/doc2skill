from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
import json
import textwrap

from .spec import build_openapi_spec


def render_package_files(package_plan: Mapping[str, Any]) -> dict[str, str]:
    skill_name = str(package_plan.get("skill_name", "docskill-factory"))
    project_name = str(package_plan.get("project_name", skill_name))
    entry_url = str(package_plan.get("entry_url", ""))
    capability_model = list(package_plan.get("capability_model", []))
    included_pages = list(package_plan.get("included_pages", []))
    file_tree = list(package_plan.get("file_tree") or [])
    constraints = dict(package_plan.get("constraints", {}))

    files: dict[str, str] = {}
    for relative_path in file_tree:
        if relative_path == "project/SKILL.md":
            files[relative_path] = render_skill_md(skill_name, entry_url, capability_model, included_pages)
        elif relative_path == "project/README.md":
            files[relative_path] = render_readme_md(skill_name, project_name, entry_url, capability_model)
        elif relative_path == "project/pyproject.toml":
            files[relative_path] = render_pyproject_toml(skill_name, project_name)
        elif relative_path == "project/.env.example":
            files[relative_path] = render_env_example(entry_url, skill_name, constraints)
        elif relative_path == "project/schema/openapi.json":
            files[relative_path] = json.dumps(build_openapi_spec(), indent=2, ensure_ascii=False) + "\n"
        elif relative_path == "project/src/docskill_factory/__init__.py":
            files[relative_path] = render_package_init(skill_name, entry_url)
        elif relative_path == "project/src/docskill_factory/spec.py":
            files[relative_path] = render_package_spec(skill_name, entry_url, capability_model)
        elif relative_path == "project/src/docskill_factory/runtime.py":
            files[relative_path] = render_package_runtime(skill_name, entry_url, capability_model)
        elif relative_path == "project/src/docskill_factory/renderer.py":
            files[relative_path] = render_package_renderer(skill_name)
        elif relative_path == "project/tests/test_spec.py":
            files[relative_path] = render_generated_test_spec()
        elif relative_path == "project/tests/test_runtime.py":
            files[relative_path] = render_generated_test_runtime()
        elif relative_path == "project/tests/notebook_tests.ipynb":
            files[relative_path] = render_notebook_tests(skill_name, entry_url)
        elif relative_path == "project/examples/discover_and_generate.py":
            files[relative_path] = render_example_discover_and_generate(skill_name, entry_url)
        elif relative_path == "project/examples/package_validation.py":
            files[relative_path] = render_example_package_validation(skill_name, entry_url)
        else:
            files[relative_path] = f"# Placeholder for {relative_path}\n"

    return files



def render_skill_md(
    skill_name: str,
    entry_url: str,
    capability_model: list[Mapping[str, Any]],
    included_pages: list[Mapping[str, Any]],
) -> str:
    capability_lines = [
        f"- {cap.get('name', 'unknown')}: {cap.get('purpose', '').strip()}"
        for cap in capability_model
    ] or ["- No capabilities extracted yet."]
    page_lines = [
        f"- {page.get('title', 'Untitled')} ({page.get('kind', 'documentation')})"
        for page in included_pages
    ] or ["- No included pages yet."]
    lines = [
        "---",
        f"name: {skill_name}",
        "description: Use when converting official documentation into a reusable skill package.",
        "---",
        "",
        "# Document Link Skill Factory",
        "",
        "## Overview",
        "",
        "This generated skill is driven by a discovered documentation entry URL and a capability model.",
        "",
        "## Entry URL",
        entry_url,
        "",
        "## Included Pages",
        *page_lines,
        "",
        "## Capabilities",
        *capability_lines,
        "",
    ]
    return "\n".join(lines)



def render_readme_md(
    skill_name: str,
    project_name: str,
    entry_url: str,
    capability_model: list[Mapping[str, Any]],
) -> str:
    capability_summary = [f"- {cap.get('name', 'unknown')}" for cap in capability_model] or [
        "- No capabilities extracted yet."
    ]
    lines = [
        f"# {skill_name}",
        "",
        "Reusable workflow for converting a documentation entry URL into a skill package.",
        "",
        "## Installation",
        "```bash",
        "pip install -e .",
        "```",
        "",
        "## Usage",
        "```bash",
        f"docskill-factory {entry_url} --skill-name {skill_name} --output-dir ./build",
        "```",
        "",
        f"This command creates `./build/{skill_name}/` and writes the package under `./build/{skill_name}/project/`.",
        "",
        "## Generated Project",
        project_name,
        "",
        "## Capabilities",
        *capability_summary,
        "",
    ]
    return "\n".join(lines)



def render_pyproject_toml(skill_name: str, project_name: str) -> str:
    return textwrap.dedent(
        f"""\
        [build-system]
        requires = ["setuptools>=68", "wheel"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "{project_name}"
        version = "0.1.0"
        description = "Reusable workflow for turning documentation links into skills"
        requires-python = ">=3.9"
        dependencies = []

        [tool.setuptools]
        package-dir = {{"" = "src"}}

        [tool.setuptools.packages.find]
        where = ["src"]
        """
    )



def render_env_example(entry_url: str, skill_name: str, constraints: Mapping[str, Any]) -> str:
    return textwrap.dedent(
        f"""\
        DOC_URL={entry_url}
        TARGET_LANGUAGE={constraints.get('target_language', 'python')}
        TARGET_SKILL_FORMAT={constraints.get('target_skill_format', 'openapi')}
        ALLOW_THIRD_PARTY_LIBS={int(bool(constraints.get('allow_third_party_libs', True)))}
        CACHE_DIR=.cache/docskill
        INDEX_DIR=.cache/docskill/index
        VECTORIZE_INDEX={int(bool(constraints.get('enable_vector_index', False)))}
        OUTPUT_DIR={constraints.get('output_dir', './build')}
        SKILL_NAME={skill_name}
        LOG_LEVEL=INFO
        """
    )



def render_package_init(skill_name: str, entry_url: str) -> str:
    return textwrap.dedent(
        f"""\
        from __future__ import annotations

        __all__ = ["__version__", "SKILL_NAME", "ENTRY_URL"]

        __version__ = "0.1.0"
        SKILL_NAME = {skill_name!r}
        ENTRY_URL = {entry_url!r}
        """
    )



def render_package_spec(skill_name: str, entry_url: str, capability_model: list[Mapping[str, Any]]) -> str:
    capabilities = [cap.get("name", "unknown") for cap in capability_model]
    return textwrap.dedent(
        f"""\
        from __future__ import annotations

        SKILL_NAME = {skill_name!r}
        ENTRY_URL = {entry_url!r}
        CAPABILITIES = {capabilities!r}


        def get_skill_metadata() -> dict:
            return {{
                "name": SKILL_NAME,
                "entry_url": ENTRY_URL,
                "capabilities": CAPABILITIES,
            }}
        """
    )



def render_package_runtime(skill_name: str, entry_url: str, capability_model: list[Mapping[str, Any]]) -> str:
    capabilities = [dict(cap) for cap in capability_model]
    return textwrap.dedent(
        f"""\
        from __future__ import annotations

        from typing import Any, Mapping

        from .spec import get_skill_metadata

        PACKAGE_METADATA = get_skill_metadata()
        CAPABILITY_MODEL = {capabilities!r}


        def dispatch_action(action_name: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
            payload = dict(payload or {{}})
            return {{
                "action": action_name,
                "payload": payload,
                "skill_name": PACKAGE_METADATA["name"],
                "entry_url": PACKAGE_METADATA["entry_url"],
                "capabilities": CAPABILITY_MODEL,
            }}
        """
    )



def render_package_renderer(skill_name: str) -> str:
    return textwrap.dedent(
        f"""\
        from __future__ import annotations

        from pathlib import Path


        def render_output_directory(path: str | Path) -> Path:
            output_path = Path(path)
            output_path.mkdir(parents=True, exist_ok=True)
            return output_path
        """
    )



def render_generated_test_spec() -> str:
    return textwrap.dedent(
        """\
        from __future__ import annotations

        from docskill_factory.spec import CAPABILITIES, ENTRY_URL, SKILL_NAME, get_skill_metadata


        def test_generated_skill_metadata_is_present() -> None:
            metadata = get_skill_metadata()
            assert metadata["name"] == SKILL_NAME
            assert metadata["entry_url"] == ENTRY_URL
            assert isinstance(CAPABILITIES, list)
        """
    )



def render_generated_test_runtime() -> str:
    return textwrap.dedent(
        """\
        from __future__ import annotations

        from docskill_factory.runtime import dispatch_action


        def test_generated_runtime_returns_metadata() -> None:
            response = dispatch_action("demo", {"value": 1})
            assert response["action"] == "demo"
            assert response["payload"]["value"] == 1
            assert "skill_name" in response
        """
    )



def render_notebook_tests(skill_name: str, entry_url: str) -> str:
    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {"id": "generated-md-1", "language": "markdown"},
                "source": [
                    f"# {skill_name} notebook checks",
                    "",
                    "This notebook validates the generated skill package.",
                ],
            },
            {
                "cell_type": "code",
                "metadata": {"id": "generated-code-1", "language": "python"},
                "source": [
                    "from docskill_factory.spec import get_skill_metadata",
                    "",
                    "print(get_skill_metadata()['name'])",
                    f"print({entry_url!r})",
                ],
            },
        ],
        "metadata": {
            "language_info": {"name": "python"},
            "generated_at": datetime.utcnow().isoformat() + "Z",
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return json.dumps(notebook, indent=2, ensure_ascii=False) + "\n"



def render_example_discover_and_generate(skill_name: str, entry_url: str) -> str:
    return textwrap.dedent(
        f"""\
        from __future__ import annotations

        from docskill_factory.runtime import dispatch_action


        def main() -> None:
            plan = dispatch_action(
                "design_skill_package",
                {{
                    "entry_url": {entry_url!r},
                    "project_name": {skill_name!r},
                    "skill_name": {skill_name!r},
                    "normalized_pages": [],
                    "capability_model": [],
                }},
            )
            files = dispatch_action("generate_skill_files", {{"package_plan": plan["package_plan"]}})
            print(plan["package_plan"]["skill_name"])
            print(len(files["files"]))


        if __name__ == "__main__":
            main()
        """
    )



def render_example_package_validation(skill_name: str, entry_url: str) -> str:
    return textwrap.dedent(
        f"""\
        from __future__ import annotations

        from docskill_factory.runtime import dispatch_action


        def main() -> None:
            plan = dispatch_action(
                "design_skill_package",
                {{
                    "entry_url": {entry_url!r},
                    "project_name": {skill_name!r},
                    "skill_name": {skill_name!r},
                    "normalized_pages": [],
                    "capability_model": [],
                }},
            )
            files = dispatch_action("generate_skill_files", {{"package_plan": plan["package_plan"]}})
            result = dispatch_action("validate_skill_package", {{"package_plan": plan["package_plan"], "files": files["files"]}})
            print(result["valid"])
            print(result["missing_files"])


        if __name__ == "__main__":
            main()
        """
    )
