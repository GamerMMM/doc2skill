import docskill_factory.runtime as runtime


def dispatch_action(action_name, payload):
    dispatcher = getattr(runtime, 'dispatch_action', None)
    if callable(dispatcher):
        return dispatcher(action_name, payload)

    action = getattr(runtime, action_name, None)
    if callable(action):
        return action(**payload)

    raise AttributeError(
        f"docskill_factory.runtime does not provide dispatch_action() or an action named {action_name!r}"
    )

def dispatch_action(action, payload):
    runtime_dispatch_action = getattr(runtime, 'dispatch_action', None)
    if callable(runtime_dispatch_action):
        return runtime_dispatch_action(action, payload)

    raise RuntimeError(
        "This example requires docskill_factory.runtime.dispatch_action(), "
        "but the installed docskill_factory.runtime module does not provide it."
    )
plan = dispatch_action('design_skill_package', {'entry_url': 'https://example.com/docs', 'normalized_pages': [], 'capability_model': []})
files = dispatch_action('generate_skill_files', {'package_plan': plan['package_plan']})
print(dispatch_action('validate_skill_package', {'package_plan': plan['package_plan'], 'files': files['files']}))
