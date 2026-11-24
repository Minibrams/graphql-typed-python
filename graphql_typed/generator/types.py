"""Shared rendering of schema inputs, selection dictionaries and response fields."""

from collections.abc import Iterable, Mapping

from graphql import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLType,
    GraphQLUnionType,
    Undefined,
    get_named_type,
)


class Names:
    def __init__(self) -> None:
        self.used: set[str] = set()

    def take(self, base: str) -> str:
        if base.startswith("__"):
            base = "Operation" + base
        name = base
        index = 2
        while name in self.used:
            name = f"{base}_{index}"
            index += 1
        self.used.add(name)
        return name


def dictionary(name: str, items: Iterable[tuple[str, str, bool]], doc: str) -> str:
    lines = []
    for key, annotation, required in items:
        item = repr(annotation) if required else f"t.NotRequired[{annotation!r}]"
        lines.append(f"    {key!r}: {item},")
    # Editors read the adjacent string. Python's help() reads the class attribute.
    return (
        f"{name} = t.TypedDict({name!r}, {{\n"
        + "\n".join(lines)
        + f'\n}})\n"""{doc}"""\n{name}.__doc__ = {doc!r}'
    )


def annotation(
    type_: GraphQLType,
    leaf: str,
    *,
    variables: bool = False,
) -> str:
    nullable = not isinstance(type_, GraphQLNonNull)
    inner = type_ if nullable else type_.of_type
    if isinstance(inner, GraphQLList):
        result = f"list[{annotation(inner.of_type, leaf, variables=variables)}]"
    else:
        result = leaf
    if nullable:
        result += " | None"
    if variables:
        result += " | Variable"
    return result


def scalar(type_: GraphQLNamedType, *, input_: bool) -> str:
    if isinstance(type_, GraphQLEnumType):
        values = ", ".join(repr(value) for value in type_.values)
        return f"t.Literal[{values}]"
    return {
        "ID": "str | int" if input_ else "str",
        "String": "str",
        "Boolean": "bool",
        "Int": "int",
        "Float": "float",
    }.get(type_.name, "t.Any")


class Inputs:
    def __init__(self, schema: GraphQLSchema, names: Names, *, authoring: bool):
        self.authoring = authoring
        objects = [
            t for t in schema.type_map.values() if isinstance(t, GraphQLInputObjectType)
        ]
        self.names = {obj.name: names.take(f"{obj.name}Input") for obj in objects}
        self.definitions = [
            dictionary(
                self.names[obj.name],
                self.items(obj.fields),
                f"GraphQL input fields for {obj.name}. "
                f"Type a reusable builder as ``def make_input() -> {self.names[obj.name]}: ...``.",
            )
            for obj in objects
        ]

    def type(self, type_: GraphQLType) -> str:
        node = get_named_type(type_)
        leaf = self.names.get(node.name) or scalar(node, input_=True)

        return annotation(type_, leaf, variables=self.authoring)

    def items(
        self, fields: Mapping[str, GraphQLArgument | GraphQLInputField]
    ) -> Iterable[tuple[str, str, bool]]:
        for name, field in fields.items():
            required = (
                isinstance(field.type, GraphQLNonNull)
                and field.default_value is Undefined
            )
            yield name, self.type(field.type), required


def render_schema(schema: GraphQLSchema) -> str:
    names = Names()
    inputs = Inputs(schema, names, authoring=True)
    objects = [
        obj
        for obj in schema.type_map.values()
        if isinstance(obj, (GraphQLObjectType, GraphQLInterfaceType))
        and not obj.name.startswith("__")
    ]
    fields = {obj.name: names.take(f"{obj.name}Fields") for obj in objects}
    definitions = [
        "import typing as t\nfrom graphql_typed import Operation, Variable",
        *inputs.definitions,
    ]
    leaf_selection = names.take("LeafSelection")
    definitions.append(
        dictionary(
            leaf_selection,
            [("alias", "str", False)],
            'Rename a leaf field in the result, as in ``{"__typename": {"alias": "kind"}}``.',
        )
    )
    leaf = f"t.Literal[True] | {leaf_selection}"
    leaves = f"{leaf} | list[{leaf}]"
    for obj in objects:
        items = [("__typename", leaves, False)]
        if isinstance(obj, GraphQLInterfaceType):
            items.extend(
                (f"... on {impl.name}", fields[impl.name], False)
                for impl in schema.get_possible_types(obj)
            )
        for key, field in obj.fields.items():
            target = get_named_type(field.type)
            if isinstance(target, GraphQLUnionType):
                continue
            if not field.args and target.name not in fields:
                items.append((key, leaves, False))
                continue
            options = [("alias", "str", False)]
            required_args = False
            if field.args:
                args = names.take(f"{obj.name}_{key}Args")
                members = list(inputs.items(field.args))
                definitions.append(
                    dictionary(
                        args,
                        members,
                        f"Arguments for {obj.name}.{key}. Supply them as ``selection['args'] = args``.",
                    )
                )
                required_args = any(required for _, _, required in members)
                options.append(("args", args, required_args))
            if target.name in fields:
                options.append(("select", fields[target.name], True))
            selection = names.take(f"{obj.name}_{key}Selection")
            definitions.append(
                dictionary(
                    selection,
                    options,
                    f"Options for selecting {obj.name}.{key}. Use ``fields[{key!r}] = selection``.",
                )
            )
            single = selection
            if not required_args and target.name not in fields:
                single = f"t.Literal[True] | {single}"
            items.append((key, f"{single} | list[{single}]", False))
        definitions.append(
            dictionary(
                fields[obj.name],
                items,
                f"Select fields of {obj.name}, for example "
                f'``fields: {fields[obj.name]} = {{"__typename": True}}``.',
            )
        )

    for kind, root in [
        ("query", schema.query_type),
        ("mutation", schema.mutation_type),
    ]:
        if root:
            definitions.append(
                f"def {kind}(name: str, *, select: {fields[root.name]}) -> Operation:\n"
                f'    """Define a named {kind} in an operation factory.\n\n'
                f'    For example, ``schema.{kind}("RootType", select={{"__typename": True}})``.\n    """\n'
                f"    return Operation({kind!r}, name, select)"
            )
    return "\n\n".join(definitions) + "\n"
