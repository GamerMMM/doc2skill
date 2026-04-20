---
name: document-link-skill-factory
description: Use when converting an official documentation URL into a reusable skill package, especially when the source site has tutorials, guides, examples, quickstarts, walkthroughs, or mixed tutorial/reference navigation.
---

# Document Link Skill Factory

## Overview
This skill turns a documentation entry URL into a reusable skill package.
It separates the work into discovery, extraction, abstraction, package design, file generation, and validation so the result can be applied to any official docs site.

## Where To Look
- `schema/openapi.json` for the generic workflow contract.
- `src/novae_skill/spec.py` for the page model, capability model, and package plan schema.
- `src/novae_skill/runtime.py` for the pure-Python workflow helpers.

## When To Use
- Converting any official docs entry page into a skill.
- Finding tutorials, guides, examples, quickstarts, walkthroughs, or how-to pages behind a docs navigation tree.
- Producing a package that another agent can install, test, and call directly.

## Guardrails
- Do not hardcode one product’s API into the skill contract.
- Keep page discovery and capability extraction generic; treat site-specific details as inputs, not assumptions.
- Record unknowns explicitly when the docs do not support a confident abstraction.

