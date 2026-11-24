"""Shared rendering of schema inputs, selection dictionaries and response fields."""

from collections.abc import Iterable, Mapping

from graphql import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLType,
    Undefined,
    get_named_type,
    is_abstract_type,
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


def dictionary(name: str, items: Iterable[tuple[str, str, bool]]) -> str:
    lines = []
    for key, annotation, required in items:
        item = repr(annotation) if required else f"t.NotRequired[{annotation!r}]"
        lines.append(f"    {key!r}: {item},")
    return f"{name} = t.TypedDict({name!r}, {{\n" + "\n".join(lines) + "\n})"


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
            dictionary(self.names[obj.name], self.items(obj.fields)) for obj in objects
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
        if isinstance(obj, GraphQLObjectType) and not obj.name.startswith("__")
    ]
    fields = {obj.name: names.take(f"{obj.name}Fields") for obj in objects}
    definitions = [
        "import typing as t\nfrom graphql_typed import Operation, Variable",
        *inputs.definitions,
    ]
    leaf_selection = names.take("LeafSelection")
    definitions.append(dictionary(leaf_selection, [("alias", "str", False)]))
    leaf = f"t.Literal[True] | {leaf_selection}"
    leaves = f"{leaf} | list[{leaf}]"
    for obj in objects:
        items = [("__typename", leaves, False)]
        for key, field in obj.fields.items():
            target = get_named_type(field.type)
            if is_abstract_type(target):
                continue
            if not field.args and not isinstance(target, GraphQLObjectType):
                items.append((key, leaves, False))
                continue
            options = [("alias", "str", False)]
            required_args = False
            if field.args:
                args = names.take(f"{obj.name}_{key}Args")
                members = list(inputs.items(field.args))
                definitions.append(dictionary(args, members))
                required_args = any(required for _, _, required in members)
                options.append(("args", args, required_args))
            if isinstance(target, GraphQLObjectType):
                options.append(("select", fields[target.name], True))
            selection = names.take(f"{obj.name}_{key}Selection")
            definitions.append(dictionary(selection, options))
            single = selection
            if not required_args and not isinstance(target, GraphQLObjectType):
                single = f"t.Literal[True] | {single}"
            items.append((key, f"{single} | list[{single}]", False))
        definitions.append(dictionary(fields[obj.name], items))

    for kind, root in [
        ("query", schema.query_type),
        ("mutation", schema.mutation_type),
    ]:
        if root:
            definitions.append(
                f"def {kind}(name: str, *, select: {fields[root.name]}) -> Operation:\n"
                f"    return Operation({kind!r}, name, select)"
            )
    return "\n\n".join(definitions) + "\n"
