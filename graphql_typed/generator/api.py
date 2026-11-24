import keyword
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from graphql import print_schema

from graphql_typed.generator.loader import load_schema
from graphql_typed.generator.types import render_schema
from graphql_typed.generator.write import publish


def generate(
    source: str | Path,
    out: str | Path,
    *,
    operations: str | None = None,
    verify_ssl: bool = True,
) -> None:
    """Generate a Python package from SDL, introspection JSON, or an endpoint URL.

    Use ``generate("schema.graphql", "generated")`` to start writing selections.
    Add ``operations="operations:operations"`` to generate clients for that factory.
    """
    output = Path(out).resolve()
    if not output.name.isidentifier() or keyword.iskeyword(output.name):
        raise ValueError(f"Output directory must name a Python package: {output}")
    schema = load_schema(str(source), verify_ssl=verify_ssl)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary) / output.name
        stage.mkdir()
        (stage / "__init__.py").touch()
        (stage / "py.typed").touch()
        (stage / "schema.py").write_text(render_schema(schema), encoding="utf-8")
        if operations is not None:
            root = output.parent
            while (root / "__init__.py").is_file():
                root = root.parent
            package = ".".join(output.relative_to(root).parts)
            (stage.parent / "source.graphql").write_text(
                print_schema(schema), encoding="utf-8"
            )
            env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(root), *sys.path])}
            run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "graphql_typed.generator.factory",
                    str(stage),
                    package,
                    operations,
                ],
                check=False,
                env=env,
                text=True,
                stderr=subprocess.PIPE,
            )
            if run.returncode:
                raise ValueError(f"Operation generation failed:\n{run.stderr.strip()}")
            shutil.copyfile(
                Path(__file__).parents[1] / "templates/transport.py",
                stage / "transport.py",
            )

        publish(stage, output)
