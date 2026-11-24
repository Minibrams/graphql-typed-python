"""Evaluate the user's factory against the freshly staged schema in a fresh interpreter."""

import importlib
import importlib.util
import sys
from pathlib import Path

from graphql import build_schema

from graphql_typed.generator.client import render_client


def compile_factory(stage: Path, package: str, factory: str) -> None:
    module, sep, function = factory.partition(":")
    if not sep or not module or not function:
        raise ValueError("Expected --operations module:function")

    # A finder also handles nested output packages and imports made by shared helpers.
    class StagedPackage:
        @staticmethod
        def find_spec(fullname: str, path=None, target=None):
            if fullname == package:
                return importlib.util.spec_from_file_location(
                    package,
                    stage / "__init__.py",
                    submodule_search_locations=[str(stage)],
                )

    sys.meta_path.insert(0, StagedPackage())
    # Re-read user modules even after a same-size edit within one timestamp tick.
    sys.pycache_prefix = str(stage.parent / "cache")
    sys.dont_write_bytecode = True
    operations = getattr(importlib.import_module(module), function)()
    schema = build_schema((stage.parent / "source.graphql").read_text(encoding="utf-8"))
    types, client = render_client(schema, operations)
    (stage / "types.py").write_text(types, encoding="utf-8")
    (stage / "client.py").write_text(client, encoding="utf-8")


if __name__ == "__main__":
    compile_factory(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
