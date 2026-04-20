from __future__ import annotations

import argparse
import json
from pathlib import Path

from .spec import build_openapi_spec, build_default_file_tree, dump_openapi_spec


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the document-link skill factory contract.")
    parser.add_argument("--spec", action="store_true", help="Print the OpenAPI-style schema.")
    parser.add_argument("--file-tree", action="store_true", help="Print the default generated file tree.")
    parser.add_argument("--write-spec", type=Path, help="Write the OpenAPI schema to a file.")
    args = parser.parse_args()

    if args.write_spec is not None:
        dump_openapi_spec(args.write_spec)
        print(str(args.write_spec))
        return 0

    if args.file_tree:
        print(json.dumps({"file_tree": build_default_file_tree()}, indent=2))
        return 0

    if args.spec:
        print(json.dumps(build_openapi_spec(), indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
