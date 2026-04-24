from __future__ import annotations

from docskill_factory.runtime import dispatch_action


def test_dispatch_actions_are_pure_transforms() -> None:
    pages = [{'title': 'Guide', 'url': 'https://example.com/guide', 'kind': 'guide', 'priority': 'high', 'evidence': ['nav'], 'reason': 'official'}]
    discovered = dispatch_action('discover_document_pages', {'entry_url': 'https://example.com', 'candidate_links': pages})
    assert discovered['page_count'] == 1
    classified = dispatch_action('classify_document_pages', {'pages': pages})
    assert classified['kept_count'] == 1
