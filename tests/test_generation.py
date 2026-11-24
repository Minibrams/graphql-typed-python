import json
from pathlib import Path

import pytest
from graphql import GraphQLError, build_schema, introspection_from_schema

from graphql_typed import Operation, var
from graphql_typed.generator import generate
from graphql_typed.generator.client import render_client
from tests.conftest import CONTRACTS

SMALL = """
type Query { foo(a: String, b: String!, id: ID): String, search: [Hit] }
type Device { serial: String }
type Site { address: String }
union Hit = Device | Site
"""


@pytest.mark.parametrize(
    ("select", "message"),
    [
        (
            {"foo": {"args": {"a": var("q"), "b": var("q")}}},
            r"foo\(a\) expects String, Query.foo\(b\) expects String!",
        ),
        (
            {"foo": {"args": {"id": var("q"), "b": var("q")}}},
            r"expects ID, Query.foo\(b\) expects String!",
        ),
        ({"foo": True}, "is required"),
        ({"foo": [{"args": {"b": "a"}}, {"args": {"b": "b"}}]}, "conflict"),
        ({"search": {"select": {"serial": True}}}, "abstract result type Hit"),
        ({"foo": {"args": {"b": 1}}}, "String cannot represent"),
        ({"foo": []}, "empty selection list"),
        ({"foo": {"alias": "a b"}}, "Names must"),
        ({}, "select at least one field"),
    ],
)
def test_invalid_operations(select, message):
    with pytest.raises((GraphQLError, ValueError), match=message):
        render_client(build_schema(SMALL), [Operation("query", "Q", select)])


def test_unique_operations():
    op = Operation("query", "Same", {"foo": {"args": {"b": "a"}}})
    with pytest.raises(ValueError, match="Duplicate operation name 'Same'"):
        render_client(build_schema(SMALL), [op, op])


def test_local_introspection(tmp_path: Path):
    sdl = CONTRACTS / "mutations/schema.graphql"
    introspection = introspection_from_schema(build_schema(sdl.read_text()))
    generate(sdl, tmp_path / "sdl")
    for label, body in [("raw", introspection), ("envelope", {"data": introspection})]:
        source = tmp_path / f"{label}.json"
        source.write_text(json.dumps(body))
        generate(source, tmp_path / label)
        assert (tmp_path / label / "schema.py").read_bytes() == (
            tmp_path / "sdl/schema.py"
        ).read_bytes()


def test_regeneration(tmp_path: Path):
    project = tmp_path / "app"
    project.mkdir()
    (project / "__init__.py").touch()
    out = project / "generated"
    sdl = project / "schema.graphql"
    sdl.write_text(SMALL)
    generate(sdl, out)
    assert not (out / "client.py").exists()
    source = project / "queries.py"
    source.write_text(
        "from app.generated import schema\ndef operations():\n    return [schema.query('Q',select={'foo':{'args':{'b':'x'}}})]\n"
    )
    generate(sdl, out, operations="app.queries:operations")
    old = {p: p.read_bytes() for p in out.glob("*.py")}
    source.write_text("def operations():\n    raise ValueError('broken factory')\n")
    with pytest.raises(ValueError, match="broken factory"):
        generate(sdl, out, operations="app.queries:operations")
    assert old == {p: p.read_bytes() for p in out.glob("*.py")}
    (out / "types.py").write_text("user_content = True")
    source.write_text("def operations():\n    return []\n")
    with pytest.raises(ValueError, match="Refusing to replace user file"):
        generate(sdl, out, operations="app.queries:operations")
    assert (out / "types.py").read_text() == "user_content = True"


def test_rapid_same_size_factory_edit(tmp_path: Path):
    import os

    source = tmp_path / "schema.graphql"
    source.write_text("type Query { a: String, b: String }")
    factory = tmp_path / "operations.py"
    op = "from generated import schema\ndef operations(): return [schema.query('Q',select={'a':True})]\n"
    factory.write_text(op)
    generated = tmp_path / "generated"
    generate(source, generated, operations="operations:operations")
    timestamp = factory.stat().st_mtime
    factory.write_text(op.replace("'a'", "'b'"))
    os.utime(factory, (timestamp, timestamp))
    generate(source, generated, operations="operations:operations")
    assert "'b': " in (generated / "types.py").read_text()
    assert "'a': " not in (generated / "types.py").read_text()


def test_publish_restores_previous_package_on_write_failure(
    tmp_path: Path, monkeypatch
):
    from graphql_typed.generator.write import publish

    out = tmp_path / "generated"
    stage = tmp_path / "stage"
    stage.mkdir()
    for file in ("client.py", "types.py"):
        (stage / file).write_text("old = True")
    publish(stage, out)
    original = {p.name: p.read_bytes() for p in out.glob("*.py")}
    for file in original:
        (stage / file).write_text("new = True")
    replace = Path.replace

    def fail_on_types(file, dest):
        if file.name == "types.py":
            raise OSError("write failed")
        return replace(file, dest)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", fail_on_types)
        with pytest.raises(OSError, match="write failed"):
            publish(stage, out)
    assert original == {p.name: p.read_bytes() for p in out.glob("*.py")}


def test_custom_scalar_variables_need_a_schema_position():
    schema = build_schema("scalar JSON\ntype Query { data(filter: JSON): String }")
    with pytest.raises(TypeError, match="inside a scalar literal"):
        render_client(
            schema,
            [
                Operation(
                    "query",
                    "Q",
                    {"data": {"args": {"filter": {"unknown": var("nested")}}}},
                )
            ],
        )
