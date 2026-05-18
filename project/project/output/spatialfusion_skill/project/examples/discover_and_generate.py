def dispatch_action(action, payload):
    return {'action': action, 'payload': payload}
entry_url = 'https://example.com/docs/'
pages = [
    {'title': 'Quickstart', 'url': 'https://example.com/docs/quickstart/', 'kind': 'quickstart', 'priority': 'high', 'evidence': ['sidebar'], 'reason': 'contains setup steps'},
]
print(dispatch_action('discover_document_pages', {'entry_url': entry_url, 'candidate_links': pages}))
