# Document Link Skill Factory

This repository contains a Python implementation of a reusable workflow for converting an official documentation entry URL into a skill package.

## What Is Included
- A docs discovery and prioritization model for tutorials, guides, examples, quickstarts, walkthroughs, and how-to pages.
- An OpenAPI-style schema for the generic workflow stages.
- A Python runtime with pure data transforms for page catalogs, capability models, and package plans.
- Notebook-based tests and example scripts that use synthetic documentation inputs.

## Installation

```bash
pip install -e .
```

For runtime execution against this workflow package:

```bash
pip install -e '.[runtime]'
```

## Configuration

Copy `.env.example` and adjust the values for your environment. The most useful settings are:
- `DOC_URL`
- `TARGET_LANGUAGE`
- `TARGET_SKILL_FORMAT`
- `ALLOW_THIRD_PARTY_LIBS`
- `CACHE_DIR`
- `OUTPUT_DIR`

## Testing

The project includes:
- `tests/test_spec.py` for schema checks.
- `tests/test_runtime.py` for workflow helper checks.
- `tests/notebook_tests.ipynb` for notebook-based validation.

## Design Notes

The docs are reduced to a capability model rather than copied verbatim. The main abstractions are: page discovery, page prioritization, capability extraction, capability normalization, skill-package design, file-tree generation, and package validation.
