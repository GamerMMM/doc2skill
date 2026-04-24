from docskill_factory.runtime import dispatch_action

plan = dispatch_action('design_skill_package', {'entry_url': 'https://example.com/docs', 'normalized_pages': [], 'capability_model': []})
files = dispatch_action('generate_skill_files', {'package_plan': plan['package_plan']})
print(dispatch_action('validate_skill_package', {'package_plan': plan['package_plan'], 'files': files['files']}))
