from collections.abc import Iterable
from functools import cache

from graphql import (
    FieldNode,
    GraphQLInterfaceType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    SelectionSetNode,
    get_named_type,
)
from graphql.execution.collect_fields import collect_fields

from graphql_typed import Operation
from graphql_typed.generator.operations import Document
from graphql_typed.generator.types import Inputs, Names, annotation, dictionary, scalar


def response(
    name: str,
    schema: GraphQLSchema,
    parent: GraphQLObjectType | GraphQLInterfaceType,
    selection_set: SelectionSetNode,
    names: Names,
    definitions: list[str],
) -> None:
    # A shared relationship has the same selected children in multiple variants.
    @cache
    def nested_type(
        key: str,
        target: GraphQLObjectType | GraphQLInterfaceType,
        nodes: tuple[FieldNode, ...],
    ) -> str:
        nested = names.take(f"{name}_{key}")
        children = tuple(
            child
            for node in nodes
            if node.selection_set
            for child in node.selection_set.selections
        )
        response(
            nested,
            schema,
            target,
            SelectionSetNode(selections=children),
            names,
            definitions,
        )
        return nested

    abstract = isinstance(parent, GraphQLInterfaceType)
    implementations = schema.get_possible_types(parent) if abstract else (parent,)
    variants = []
    for obj in implementations:
        variant = names.take(f"{name}_{obj.name}") if abstract else name
        variants.append(variant)
        items = []
        for key, nodes in collect_fields(schema, {}, {}, obj, selection_set).items():
            field_name = nodes[0].name.value
            if field_name == "__typename":
                item_type = f"t.Literal[{obj.name!r}]"
            else:
                field_type = obj.fields[field_name].type
                target = get_named_type(field_type)
                if isinstance(target, (GraphQLObjectType, GraphQLInterfaceType)):
                    leaf = nested_type(key, target, tuple(nodes))
                else:
                    leaf = scalar(target, input_=False)
                item_type = annotation(field_type, leaf)
            items.append((key, item_type, True))
        definitions.append(dictionary(variant, items))
    if abstract:
        definitions.append(f"{name} = {' | '.join(variants) or 't.Never'}")


def render_client(
    schema: GraphQLSchema, operations: Iterable[Operation]
) -> tuple[str, str]:
    names = Names()
    inputs = Inputs(schema, names, authoring=False)
    types = ["import typing as t", *inputs.definitions]
    client = [
        (
            "from __future__ import annotations\nimport typing as t\n"
            "from . import types\nfrom .transport import AsyncExecutor, SyncExecutor"
        )
    ]
    documents: dict[str, dict[str, str]] = {"query": {}, "mutation": {}}
    seen: set[str] = set()
    for op in operations:
        if not isinstance(op, Operation):
            raise TypeError("Operation factory must return an iterable of operations")
        if op.name in seen:
            raise ValueError(f"Duplicate operation name {op.name!r}")
        seen.add(op.name)
        doc = Document(schema, op)
        documents[op.kind][op.name] = doc.text
        data = names.take(op.name + "Data")
        assert doc.root is not None
        response(data, schema, doc.root, doc.selection_set, names, types)
        params = ""
        if doc.variables:
            variables = names.take(op.name + "Variables")
            fields = [
                (k, inputs.type(v), isinstance(v, GraphQLNonNull))
                for k, v in doc.variables.items()
            ]
            types.append(dictionary(variables, fields))
            default = "" if any(required for _, _, required in fields) else " = ..."
            params = f", *, variables: types.{variables}{default}"
        for prefix, modifier in [("Sync", ""), ("Async", "async ")]:
            client.append(
                f"class {prefix}_{op.name}(t.Protocol):\n"
                f"    {modifier}def __call__(self{params}) -> types.{data}: ..."
            )

    for kind, docs in documents.items():
        if docs:
            entries = "\n".join(f"    {key!r}: {text!r}," for key, text in docs.items())
            client.append(f"_{kind}: dict[str, str] = {{\n{entries}\n}}")
    for prefix, class_name in [("Sync", "Client"), ("Async", "AsyncClient")]:
        methods = []
        for kind, docs in documents.items():
            if not docs:
                continue
            bind = f"self._bind(name, _{kind})"
            for name in docs:
                protocol = f"{prefix}_{name}"
                signature = (
                    f"    def {kind}(self, name: t.Literal[{name!r}]) -> {protocol}:"
                )
                if len(docs) == 1:
                    methods.extend(
                        [signature, f"        return t.cast({protocol}, {bind})"]
                    )
                else:
                    methods.extend(["    @t.overload", signature + " ..."])
            if len(docs) > 1:
                methods.extend(
                    [
                        f"    def {kind}(self, name: str) -> t.Any:",
                        f"        return {bind}",
                    ]
                )
        client.append(
            f"class {class_name}({prefix}Executor):\n"
            + ("\n".join(methods) or "    pass")
        )
    return "\n\n".join(types) + "\n", "\n\n".join(client) + "\n"
