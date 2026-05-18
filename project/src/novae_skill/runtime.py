from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
import json
import re
from copy import deepcopy

from .renderer import render_package_files
from .spec import (
    CORE_ACTIONS,
    DEFAULT_DISCOVERY_HINTS,
    DEFAULT_EXCLUDE_KINDS,
    DEFAULT_EXCLUSION_HINTS,
    DEFAULT_FILE_TREE,
    DEFAULT_INCLUDE_KINDS,
    CapabilityRecord,
    PageRecord,
    SkillConstraint,
    SkillPackagePlan,
    build_default_file_tree,
)

USER_AGENT = "docskill-factory/0.1.0"
DEFAULT_TIMEOUT_SECONDS = 10
_GITHUB_EXCLUDED_PATH_PREFIXES = {
    "blob",
    "tree",
    "issues",
    "pull",
    "pulls",
    "releases",
    "discussions",
    "actions",
    "wiki",
    "projects",
}


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._current_link: dict[str, str] | None = None
        self._capture_title = False
        self.page_title = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "a" and attr_map.get("href"):
            self._current_link = {
                "href": attr_map.get("href", ""),
                "text": "",
                "title": attr_map.get("title", ""),
                "rel": attr_map.get("rel", ""),
            }
        elif tag == "title":
            self._capture_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_link is not None:
            self.links.append(self._current_link)
            self._current_link = None
        elif tag == "title":
            self._capture_title = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._current_link is not None:
            current_text = self._current_link.get("text", "")
            self._current_link["text"] = f"{current_text} {text}".strip()
        if self._capture_title:
            self.page_title = f"{self.page_title} {text}".strip()



def dispatch_action(action_name: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    action_map = {
        "discover_document_pages": discover_document_pages_action,
        "classify_document_pages": classify_document_pages_action,
        "extract_document_capabilities": extract_document_capabilities_action,
        "normalize_capabilities": normalize_capabilities_action,
        "design_skill_package": design_skill_package_action,
        "generate_skill_files": generate_skill_files_action,
        "validate_skill_package": validate_skill_package_action,
    }
    if action_name not in action_map:
        raise ValueError(f"Unknown action: {action_name}")
    return action_map[action_name](dict(payload or {}))



def discover_document_pages_action(payload: Mapping[str, Any]) -> dict[str, Any]:
    entry_url = str(payload.get("entry_url", "")).strip()
    if not entry_url:
        raise ValueError("entry_url is required")

    navigation_hints = _normalize_string_list(payload.get("navigation_hints", DEFAULT_DISCOVERY_HINTS))
    exclusion_hints = _normalize_string_list(payload.get("exclusion_hints", DEFAULT_EXCLUSION_HINTS))
    candidate_links = [PageRecord.from_mapping(item) for item in payload.get("candidate_links", [])]
    max_depth = int(payload.get("max_depth", 1) or 1)
    site_name = str(payload.get("site_name", "")).strip()

    if _is_github_repo_url(entry_url):
        github_result = extract_github_links(entry_url)
        discovered = [
            PageRecord.from_mapping(
                {
                    "title": f"{github_result['repo_name']} Documentation",
                    "url": github_result["repo_url"],
                    "kind": "documentation",
                    "priority": "high",
                    "evidence": ["github_repo"],
                    "reason": "Repository root",
                }
            )
        ]
        discovered.extend(PageRecord.from_mapping(page) for page in github_result["links"])
        discovered.extend(candidate_links)
        discovered = _dedupe_pages(discovered)
        scored = [
            (page, _score_page(page, navigation_hints, exclusion_hints))
            for page in discovered
        ]
        scored.sort(key=lambda item: (-item[1], item[0].title.lower(), item[0].url))
        pages = [dict(_page_to_dict(page), score=score) for page, score in scored]
        return {
            "entry_url": github_result["repo_url"],
            "page_count": len(pages),
            "discovered_pages": pages,
            "discovery_mode": "github",
            "site_name": site_name or github_result["repo_name"],
        }

    html = _fetch_text(entry_url)
    discovered: list[PageRecord] = []
    if candidate_links:
        discovered.extend(candidate_links)

    if html:
        parser = _LinkCollector()
        parser.feed(html)
        base_domain = urlparse(entry_url).netloc.lower()
        seen_urls = {_normalize_url(entry_url)}
        page_title = parser.page_title or site_name or _title_from_url(entry_url)
        discovered.append(
            PageRecord.from_mapping(
                {
                    "title": page_title,
                    "url": entry_url,
                    "kind": _infer_kind(page_title, entry_url),
                    "priority": "high",
                    "evidence": ["entry_page"],
                    "reason": "Entry URL",
                }
            )
        )
        depth_limit = max(1, max_depth)
        for link in parser.links:
            href = link.get("href", "").strip()
            if not href or href.startswith("javascript:") or href.startswith("mailto:"):
                continue
            absolute_url = _normalize_url(urljoin(entry_url, href))
            if absolute_url in seen_urls:
                continue
            if not _same_domain(entry_url, absolute_url):
                continue
            text = " ".join([link.get("text", ""), link.get("title", ""), absolute_url]).strip()
            if _matches_any(text, exclusion_hints):
                continue
            if not _matches_any(text, navigation_hints) and _infer_kind(text, absolute_url) == "documentation":
                if "docs" not in absolute_url.lower() and "tutorial" not in absolute_url.lower():
                    continue
            seen_urls.add(absolute_url)
            discovered.append(
                PageRecord.from_mapping(
                    {
                        "title": _title_from_link(link, absolute_url),
                        "url": absolute_url,
                        "kind": _infer_kind(text, absolute_url),
                        "priority": _priority_from_text(text),
                        "evidence": _build_evidence(link, text),
                        "reason": _reason_from_text(text),
                    }
                )
            )
            if len(discovered) >= depth_limit * 50:
                break
    else:
        discovered.append(
            PageRecord.from_mapping(
                {
                    "title": site_name or _title_from_url(entry_url),
                    "url": entry_url,
                    "kind": _infer_kind(site_name or entry_url, entry_url),
                    "priority": "high",
                    "evidence": ["entry_page"],
                    "reason": "Entry URL",
                }
            )
        )

    discovered = _dedupe_pages(discovered)
    scored = [(page, _score_page(page, navigation_hints, exclusion_hints)) for page in discovered]
    scored.sort(key=lambda item: (-item[1], item[0].title.lower(), item[0].url))
    pages = [dict(_page_to_dict(page), score=score) for page, score in scored]
    return {
        "entry_url": entry_url,
        "page_count": len(pages),
        "discovered_pages": pages,
        "discovery_mode": "web",
        "site_name": site_name or urlparse(entry_url).netloc,
    }



def classify_document_pages_action(payload: Mapping[str, Any]) -> dict[str, Any]:
    pages = [PageRecord.from_mapping(item) for item in payload.get("pages", [])]
    keep_kinds = {kind.lower() for kind in _normalize_string_list(payload.get("keep_kinds", DEFAULT_INCLUDE_KINDS))}
    exclude_kinds = {kind.lower() for kind in _normalize_string_list(payload.get("exclude_kinds", DEFAULT_EXCLUDE_KINDS))}
    prefer_code_samples = bool(payload.get("prefer_code_samples", False))
    prefer_api_dependencies = bool(payload.get("prefer_api_dependencies", False))

    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    priority_scores: list[dict[str, Any]] = []

    for page in pages:
        score = 0
        haystack = " ".join(
            [page.title, page.url, page.kind, page.priority, " ".join(page.evidence), page.reason]
        ).lower()
        kind = page.kind.lower().strip()

        if kind in keep_kinds:
            score += 4
        if kind in exclude_kinds:
            score -= 4
        if _matches_any(haystack, keep_kinds):
            score += 2
        if _matches_any(haystack, exclude_kinds):
            score -= 2
        if kind == "documentation" and ("/docs/" in page.url.lower() or "/tutorials/" in page.url.lower() or "/examples/" in page.url.lower()):
            score += 2
        if prefer_code_samples and any(token in haystack for token in ["code", "example", "sample", "snippet"]):
            score += 1
        if prefer_api_dependencies and any(token in haystack for token in ["api", "reference", "parameter"]):
            score += 1
        if "tutorial" in haystack or "quickstart" in haystack or "walkthrough" in haystack:
            score += 1
        if "marketing" in haystack or "release notes" in haystack or "blog" in haystack:
            score -= 1

        record = dict(_page_to_dict(page), score=score)
        priority_scores.append({"title": page.title, "url": page.url, "score": score})
        if score > 0:
            included.append(record)
        else:
            excluded.append(record)

    included.sort(key=lambda item: (-item["score"], item.get("priority", "medium"), item.get("title", "")))
    excluded.sort(key=lambda item: (item["score"], item.get("title", "")))

    return {
        "kept_count": len(included),
        "excluded_count": len(excluded),
        "included_pages": included,
        "excluded_pages": excluded,
        "priority_scores": priority_scores,
    }



def extract_document_capabilities_action(payload: Mapping[str, Any]) -> dict[str, Any]:
    pages = [PageRecord.from_mapping(item) for item in payload.get("pages", [])]
    page_evidence = list(payload.get("page_evidence", []))
    target_language = str(payload.get("target_language", "python"))
    constraints = dict(payload.get("constraints", {}))

    if not page_evidence:
        for page in pages:
            page_evidence.append(
                {
                    "name": _slugify(page.title or page.url),
                    "purpose": page.reason or f"Teach {page.title or page.url}",
                    "inputs": ["entry_url", target_language],
                    "outputs": ["skill content"],
                    "dependencies": list(page.evidence) or [page.kind],
                    "risk_points": ["Documentation may be incomplete"],
                    "evidence_pages": [page.url],
                    "notes": [page.title],
                }
            )

    capabilities: list[dict[str, Any]] = []
    for index, item in enumerate(page_evidence):
        if isinstance(item, Mapping):
            record = CapabilityRecord.from_mapping(item)
        else:
            record = CapabilityRecord.from_mapping({"name": f"capability_{index}", "purpose": str(item)})
        if not record.name:
            record.name = _slugify(record.purpose or f"capability_{index}")
        if not record.purpose:
            record.purpose = f"Derived capability for {record.name}"
        if not record.inputs:
            record.inputs = ["entry_url", target_language]
        if not record.outputs:
            record.outputs = ["skill package artifact"]
        if not record.dependencies:
            record.dependencies = ["documentation"]
        if not record.risk_points:
            record.risk_points = ["Unknown docs coverage"]
        if not record.evidence_pages and pages:
            record.evidence_pages = [pages[min(index, len(pages) - 1)].url]
        if not record.notes:
            record.notes = ["Automatically derived from documentation"]
        capabilities.append(_capability_to_dict(record))

    return {
        "capabilities": capabilities,
        "capability_count": len(capabilities),
        "target_language": target_language,
        "constraints": constraints,
    }



def normalize_capabilities_action(payload: Mapping[str, Any]) -> dict[str, Any]:
    capabilities = [CapabilityRecord.from_mapping(item) for item in payload.get("capabilities", [])]
    merge_strategy = str(payload.get("merge_strategy", "collapse_duplicates"))
    dedupe_keys = [str(item) for item in payload.get("dedupe_keys", ["name"])]

    if merge_strategy != "collapse_duplicates":
        normalized = [_capability_to_dict(capability) for capability in capabilities]
        return {
            "normalized_capabilities": normalized,
            "capability_count": len(normalized),
            "merge_strategy": merge_strategy,
            "dedupe_keys": dedupe_keys,
        }

    merged: dict[tuple[Any, ...], CapabilityRecord] = {}
    order: list[tuple[Any, ...]] = []
    for capability in capabilities:
        key = tuple(getattr(capability, field, None) for field in dedupe_keys)
        if key not in merged:
            merged[key] = CapabilityRecord.from_mapping(
                {
                    "name": capability.name,
                    "purpose": capability.purpose,
                    "inputs": list(capability.inputs),
                    "outputs": list(capability.outputs),
                    "dependencies": list(capability.dependencies),
                    "risk_points": list(capability.risk_points),
                    "evidence_pages": list(capability.evidence_pages),
                    "notes": list(capability.notes),
                }
            )
            order.append(key)
            continue
        existing = merged[key]
        existing.purpose = existing.purpose or capability.purpose
        existing.inputs = _unique_preserve_order(existing.inputs + capability.inputs)
        existing.outputs = _unique_preserve_order(existing.outputs + capability.outputs)
        existing.dependencies = _unique_preserve_order(existing.dependencies + capability.dependencies)
        existing.risk_points = _unique_preserve_order(existing.risk_points + capability.risk_points)
        existing.evidence_pages = _unique_preserve_order(existing.evidence_pages + capability.evidence_pages)
        existing.notes = _unique_preserve_order(existing.notes + capability.notes)

    normalized = [_capability_to_dict(merged[key]) for key in order]
    return {
        "normalized_capabilities": normalized,
        "capability_count": len(normalized),
        "merge_strategy": merge_strategy,
        "dedupe_keys": dedupe_keys,
    }



def design_skill_package_action(payload: Mapping[str, Any]) -> dict[str, Any]:
    entry_url = str(payload.get("entry_url", "")).strip()
    skill_name = str(payload.get("skill_name") or _derive_skill_name(entry_url) or "docskill-factory")
    project_name = str(payload.get("project_name") or skill_name)
    normalized_pages = [dict(item) for item in payload.get("normalized_pages", [])]
    capability_model = [dict(item) for item in payload.get("capability_model", [])]
    constraint = SkillConstraint.from_mapping(payload.get("constraints", {}))
    file_tree = list(payload.get("file_tree") or build_default_file_tree())

    if not capability_model and normalized_pages:
        capability_model = [
            {
                "name": _slugify(page.get("title", f"page_{index}")),
                "purpose": page.get("reason", f"Teach {page.get('title', 'documentation')}"),
                "inputs": ["entry_url"],
                "outputs": ["skill package artifact"],
                "dependencies": list(page.get("evidence", [])) or [page.get("kind", "documentation")],
                "risk_points": ["Documentation may be incomplete"],
                "evidence_pages": [page.get("url", entry_url)],
                "notes": [page.get("title", "")],
            }
            for index, page in enumerate(normalized_pages)
        ]

    validation_checks = [
        "project/SKILL.md exists",
        "project/schema/openapi.json exists",
        "project/tests/test_runtime.py exists",
        "project/tests/test_spec.py exists",
        "package metadata includes skill name and entry URL",
    ]

    package_plan = SkillPackagePlan.from_mapping(
        {
            "project_name": project_name,
            "skill_name": skill_name,
            "entry_url": entry_url,
            "file_tree": file_tree,
            "capability_model": capability_model,
            "included_pages": normalized_pages,
            "constraints": constraint.to_dict(),
            "install_instructions": [
                "pip install -e .",
                f"docskill-factory {entry_url} --skill-name {skill_name} --output-dir {constraint.output_dir}",
            ],
            "validation_checks": validation_checks,
        }
    )

    return {
        "package_plan": package_plan.to_dict(),
        "project_name": project_name,
        "skill_name": skill_name,
        "entry_url": entry_url,
        "file_tree": file_tree,
    }



def generate_skill_files_action(payload: Mapping[str, Any]) -> dict[str, Any]:
    package_plan = SkillPackagePlan.from_mapping(payload.get("package_plan", {}))
    files = render_package_files(package_plan.to_dict())
    return {"files": files, "package_plan": package_plan.to_dict()}



def validate_skill_package_action(payload: Mapping[str, Any]) -> dict[str, Any]:
    package_plan = SkillPackagePlan.from_mapping(payload.get("package_plan", {}))
    files = dict(payload.get("files", {}))
    validation_mode = str(payload.get("validation_mode", "standard"))

    expected_files = set(package_plan.file_tree or build_default_file_tree())
    present_files = set(files.keys())
    missing_files = sorted(expected_files - present_files)
    extra_files = sorted(present_files - expected_files)
    warnings: list[str] = []

    if package_plan.skill_name and package_plan.skill_name not in (files.get("project/SKILL.md", "") or ""):
        warnings.append("Skill name is not reflected in project/SKILL.md")
    if package_plan.entry_url and package_plan.entry_url not in (files.get("project/SKILL.md", "") or ""):
        warnings.append("Entry URL is not reflected in project/SKILL.md")
    if not package_plan.capability_model:
        warnings.append("No capabilities were captured for the generated skill package")
    if validation_mode != "standard":
        warnings.append(f"Validation mode '{validation_mode}' was requested but not specially handled")
    if extra_files:
        warnings.append(f"Generated files include {len(extra_files)} extra path(s) outside the default file tree")

    valid = not missing_files and not any(
        candidate.startswith("project/schema/") and candidate.endswith("openapi.json") is False for candidate in missing_files
    )

    if "project/schema/openapi.json" in present_files:
        try:
            json.loads(files["project/schema/openapi.json"])
        except Exception:
            valid = False
            warnings.append("project/schema/openapi.json is not valid JSON")

    return {
        "valid": valid,
        "missing_files": missing_files,
        "extra_files": extra_files,
        "warnings": warnings,
        "expected_files": sorted(expected_files),
        "present_files": sorted(present_files),
        "validation_mode": validation_mode,
    }



def extract_github_links(repo_url: str) -> dict[str, Any]:
    owner, repo = _parse_github_repo(repo_url)
    repo_root = f"https://github.com/{owner}/{repo}"
    default_branch = _github_default_branch(owner, repo) or "main"
    branch_candidates = _unique_preserve_order([default_branch, "main", "master", "trunk"])
    links: list[dict[str, Any]] = []

    links.append(
        {
            "title": f"{repo} Documentation",
            "url": repo_root,
            "kind": "documentation",
            "priority": "high",
            "source": "github_repo",
        }
    )

    for branch in branch_candidates:
        raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}"
        for readme_name in ["README.md", "readme.md", "README.rst", "readme.rst"]:
            readme_url = f"{raw_base}/{readme_name}"
            content = _fetch_text(readme_url)
            if not content:
                continue
            for link_title, link_url in _extract_markdown_links(content):
                if not _looks_documentation_like(link_title, link_url):
                    continue
                links.append(
                    {
                        "title": link_title,
                        "url": _resolve_github_url(repo_root, branch, link_url),
                        "kind": _infer_kind(link_title, link_url),
                        "priority": _priority_from_text(link_title + " " + link_url),
                        "source": "github_readme",
                    }
                )
            break
        if len(links) > 1:
            break

    releases = _fetch_github_releases(owner, repo)
    for release in releases:
        body = str(release.get("body", ""))
        for link_title, link_url in _extract_markdown_links(body):
            if not _looks_documentation_like(link_title, link_url):
                continue
            links.append(
                {
                    "title": f"{link_title} (Release)",
                    "url": _resolve_github_url(repo_root, default_branch, link_url),
                    "kind": _infer_kind(link_title, link_url),
                    "priority": _priority_from_text(link_title + " " + link_url),
                    "source": "github_release",
                }
            )

    for doc_dir in ["docs/", "doc/", "documentation/", "examples/", "tutorials/"]:
        links.append(
            {
                "title": f"{doc_dir.rstrip('/')} directory",
                "url": f"{repo_root}/tree/{default_branch}/{doc_dir.rstrip('/')}",
                "kind": "documentation",
                "priority": "high",
                "source": "github_structure",
            }
        )

    deduped = _dedupe_page_mappings(links)
    return {
        "repo_url": repo_root,
        "owner": owner,
        "repo_name": repo,
        "default_branch": default_branch,
        "links": deduped,
        "total_extracted": len(deduped),
    }



def save_files_to_directory(
    file_map: Mapping[str, str],
    output_dir: str | Path,
    skill_name: str | None = None,
) -> list[Path]:
    base_dir = Path(output_dir)
    if skill_name:
        base_dir = base_dir / skill_name
    base_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    for relative_path, content in file_map.items():
        target_path = base_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        saved_paths.append(target_path)
    return saved_paths



def _same_domain(base_url: str, candidate_url: str) -> bool:
    base = urlparse(base_url)
    candidate = urlparse(candidate_url)
    return base.netloc.lower() == candidate.netloc.lower()



def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [str(item) for item in value.values()]
    result: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            result.append(text)
    return _unique_preserve_order(result)



def _unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered



def _page_to_dict(page: PageRecord) -> dict[str, Any]:
    return {
        "title": page.title,
        "url": page.url,
        "kind": page.kind,
        "priority": page.priority,
        "evidence": list(page.evidence),
        "reason": page.reason,
    }



def _capability_to_dict(capability: CapabilityRecord) -> dict[str, Any]:
    return {
        "name": capability.name,
        "purpose": capability.purpose,
        "inputs": list(capability.inputs),
        "outputs": list(capability.outputs),
        "dependencies": list(capability.dependencies),
        "risk_points": list(capability.risk_points),
        "evidence_pages": list(capability.evidence_pages),
        "notes": list(capability.notes),
    }



def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    if path.endswith("/index.html"):
        path = path[: -len("index.html")]
    normalized = urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))
    return normalized.rstrip("/") or normalized



def _derive_skill_name(url: str) -> str:
    candidate = _derive_name_from_url(url)
    return candidate or "docskill-factory"



def _derive_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return parsed.netloc.replace(".", "-") or "docskill"
    tail = parts[-1]
    tail = re.sub(r"[^a-zA-Z0-9]+", "-", tail).strip("-")
    return tail.lower() or parsed.netloc.replace(".", "-")



def _dedupe_pages(pages: Iterable[PageRecord]) -> list[PageRecord]:
    deduped: dict[str, PageRecord] = {}
    for page in pages:
        key = _normalize_url(page.url)
        if key not in deduped:
            deduped[key] = page
            continue
        existing = deduped[key]
        existing.evidence = _unique_preserve_order(existing.evidence + page.evidence)
        if not existing.reason:
            existing.reason = page.reason
        if existing.priority == "medium" and page.priority == "high":
            existing.priority = "high"
        if existing.kind == "documentation" and page.kind != "documentation":
            existing.kind = page.kind
    return list(deduped.values())



def _dedupe_page_mappings(pages: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for page in pages:
        record = PageRecord.from_mapping(page)
        key = _normalize_url(record.url)
        if key not in deduped:
            deduped[key] = _page_to_dict(record)
            continue
        existing = deduped[key]
        existing["evidence"] = _unique_preserve_order(_normalize_string_list(existing.get("evidence", [])) + record.evidence)
        if not existing.get("reason"):
            existing["reason"] = record.reason
        if existing.get("priority") == "medium" and record.priority == "high":
            existing["priority"] = "high"
        if existing.get("kind") == "documentation" and record.kind != "documentation":
            existing["kind"] = record.kind
    return list(deduped.values())



def _score_page(page: PageRecord, navigation_hints: Iterable[str], exclusion_hints: Iterable[str]) -> int:
    score = 0
    text = " ".join([page.title, page.url, page.kind, page.priority, " ".join(page.evidence), page.reason]).lower()
    if page.kind.lower() in DEFAULT_INCLUDE_KINDS:
        score += 3
    if page.kind.lower() in DEFAULT_EXCLUDE_KINDS:
        score -= 3
    if _matches_any(text, navigation_hints):
        score += 2
    if _matches_any(text, exclusion_hints):
        score -= 2
    if "/docs/" in page.url.lower() or "/tutorial/" in page.url.lower() or "/tutorials/" in page.url.lower() or "/examples/" in page.url.lower():
        score += 1
    if any(token in text for token in ["code sample", "code examples", "quickstart", "walkthrough", "how-to"]):
        score += 1
    if any(token in text for token in ["blog", "marketing", "release notes", "changelog"]):
        score -= 1
    return score



def _matches_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword.lower() in text.lower() for keyword in keywords)



def _infer_kind(text: str, url: str) -> str:
    haystack = f"{text} {url}".lower()
    if any(token in haystack for token in ["tutorial", "getting started", "quickstart"]):
        return "tutorial"
    if any(token in haystack for token in ["walkthrough", "how-to", "guide"]):
        return "guide"
    if any(token in haystack for token in ["example", "samples", "demo"]):
        return "example"
    if "reference" in haystack or "/api" in haystack:
        return "reference"
    if any(token in haystack for token in ["changelog", "release notes", "blog", "marketing"]):
        return "documentation"
    if any(token in haystack for token in ["docs/", "/docs/", "/documentation/", "/examples/", "/tutorials/"]):
        return "documentation"
    return "documentation"



def _priority_from_text(text: str) -> str:
    haystack = text.lower()
    if any(token in haystack for token in ["tutorial", "guide", "quickstart", "walkthrough"]):
        return "high"
    if any(token in haystack for token in ["example", "how-to", "docs", "documentation"]):
        return "medium"
    return "low"



def _build_evidence(link: Mapping[str, str], text: str) -> list[str]:
    evidence = []
    if link.get("rel"):
        evidence.append(str(link["rel"]))
    if link.get("title"):
        evidence.append(str(link["title"]))
    if link.get("text"):
        evidence.append(str(link["text"]))
    if "code" in text.lower():
        evidence.append("code_samples")
    if "sidebar" in text.lower() or "nav" in text.lower():
        evidence.append("navigation")
    return _unique_preserve_order(evidence)



def _reason_from_text(text: str) -> str:
    stripped = text.strip()
    return stripped[:160] if stripped else "Discovered from documentation navigation"



def _title_from_link(link: Mapping[str, str], fallback_url: str) -> str:
    for key in ["text", "title"]:
        value = str(link.get(key, "")).strip()
        if value:
            return value
    return _title_from_url(fallback_url)



def _title_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/").split("/")[-1]
    if not path:
        return parsed.netloc or url
    return path.replace("-", " ").replace("_", " ").title()



def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_") or "capability"



def _resolve_github_url(repo_root: str, default_branch: str, url: str) -> str:
    url = url.strip()
    if not url:
        return repo_root
    if url.startswith("#"):
        return f"{repo_root}{url}"
    if url.startswith("/"):
        return f"https://github.com{url}"
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return urljoin(f"{repo_root}/blob/{default_branch}/", url)



def _looks_documentation_like(title: str, url: str) -> bool:
    haystack = f"{title} {url}".lower()
    return any(
        token in haystack
        for token in ["tutorial", "guide", "example", "quickstart", "demo", "doc", "documentation", "how-to", "walkthrough"]
    )



def _fetch_text(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str | None:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout_seconds) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            data = response.read()
            return data.decode(content_type, errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError):
        return None



def _fetch_json(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Any:
    content = _fetch_text(url, timeout_seconds)
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None



def _extract_markdown_links(content: str) -> list[tuple[str, str]]:
    return re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)



def _parse_github_repo(repo_url: str) -> tuple[str, str]:
    parsed = urlparse(repo_url)
    if "github.com" not in parsed.netloc.lower():
        raise ValueError("GitHub URL is required")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("GitHub repository URL must include owner and repo name")
    return parts[0], parts[1]



def _is_github_repo_url(repo_url: str) -> bool:
    try:
        parsed = urlparse(repo_url)
        if "github.com" not in parsed.netloc.lower():
            return False
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            return False
        return parts[0] not in _GITHUB_EXCLUDED_PATH_PREFIXES
    except Exception:
        return False



def _github_default_branch(owner: str, repo: str) -> str | None:
    repo_json = _fetch_json(f"https://api.github.com/repos/{owner}/{repo}")
    if isinstance(repo_json, Mapping):
        default_branch = repo_json.get("default_branch")
        if default_branch:
            return str(default_branch)
    return None



def _fetch_github_releases(owner: str, repo: str) -> list[dict[str, Any]]:
    releases_json = _fetch_json(f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=3")
    if isinstance(releases_json, list):
        return [dict(item) for item in releases_json if isinstance(item, Mapping)]
    return []
