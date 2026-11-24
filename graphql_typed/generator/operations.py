"""Compile a selection dictionary into a validated, named GraphQL document."""

import json
from typing import Any

from graphql import (
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLType,
    OperationDefinitionNode,
    assert_name,
    get_named_type,
    is_leaf_type,
    parse,
    print_ast,
    validate,
)

from graphql_typed import Operation, Variable


def object_value(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ValueError(f"{path}: expected a dictionary with string keys")
    return value


def literal(value: Any) -> str:
    if isinstance(value, Variable):
        raise TypeError(
            f"Cannot infer the type of ${value.name} inside a scalar literal"
        )
    if isinstance(value, dict):
        fields = (f"{assert_name(key)}: {literal(item)}" for key, item in value.items())
        return "{" + ", ".join(fields) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(literal(item) for item in value) + "]"
    return json.dumps(value, allow_nan=False)


class Document:
    def __init__(self, schema: GraphQLSchema, op: Operation):
        assert_name(op.name)
        self.schema = schema
        self.variables: dict[str, GraphQLType] = {}
        self.locations: dict[str, str] = {}
        self.root = {"query": schema.query_type, "mutation": schema.mutation_type}[
            op.kind
        ]
        if self.root is None:
            raise ValueError(f"Schema has no {op.kind} root")
        body = self.selection(self.root, op.select)
        declarations = ", ".join(f"${k}: {t}" for k, t in self.variables.items())
        signature = f"({declarations})" if declarations else ""
        ast = parse(f"{op.kind} {op.name}{signature} {body}")
        errors = validate(schema, ast)
        if errors:
            raise ValueError(
                "\n".join(f"{op.name}: {error.message}" for error in errors)
            )
        self.text = print_ast(ast)
        definition = ast.definitions[0]
        assert isinstance(definition, OperationDefinitionNode)
        self.selection_set = definition.selection_set

    def value(self, value: Any, type_: GraphQLType, path: str) -> str:
        if isinstance(value, Variable):
            name = assert_name(value.name)
            previous = self.variables.setdefault(name, type_)
            location = self.locations.setdefault(name, path)
            if str(previous) != str(type_):
                raise ValueError(
                    f"${name}: {location} expects {previous}, {path} expects {type_}"
                )
            return f"${name}"
        inner = type_.of_type if isinstance(type_, GraphQLNonNull) else type_
        if value is None:
            return "null"
        if isinstance(inner, GraphQLList):
            if isinstance(value, list):
                return (
                    "["
                    + ", ".join(
                        self.value(v, inner.of_type, path + "[]") for v in value
                    )
                    + "]"
                )
            return self.value(value, inner.of_type, path + "[]")
        if isinstance(inner, GraphQLInputObjectType):
            items = []
            for key, v in object_value(value, path).items():
                field = inner.fields.get(key)
                if field is None:
                    raise ValueError(f"{path}: unknown input field {key!r}")
                items.append(f"{key}: {self.value(v, field.type, f'{path}.{key}')}")
            return "{" + ", ".join(items) + "}"
        if isinstance(inner, GraphQLEnumType):
            return assert_name(value)
        return literal(value)

    def selection(
        self, parent: GraphQLObjectType | GraphQLInterfaceType, value: object
    ) -> str:
        parts = []
        for key, selections in object_value(value, parent.name).items():
            if isinstance(parent, GraphQLInterfaceType) and key.startswith("... on "):
                target = self.schema.get_type(key.removeprefix("... on "))
                if not isinstance(
                    target, GraphQLObjectType
                ) or not self.schema.is_sub_type(parent, target):
                    raise ValueError(
                        f"{parent.name}: invalid fragment condition {key!r}"
                    )
                parts.append(f"{key} {self.selection(target, selections)}")
                continue
            if selections == []:
                raise ValueError(f"{parent.name}.{key}: empty selection list")
            for item in selections if isinstance(selections, list) else [selections]:
                options = (
                    {} if item is True else object_value(item, f"{parent.name}.{key}")
                )
                parts.append(self.field(parent, key, options))
        if not parts:
            raise ValueError(f"{parent.name}: select at least one field")
        return "{ " + " ".join(parts) + " }"

    def field(
        self,
        parent: GraphQLObjectType | GraphQLInterfaceType,
        key: str,
        options: dict[str, Any],
    ) -> str:
        path = f"{parent.name}.{key}"
        if extra := options.keys() - {"alias", "args", "select"}:
            raise ValueError(f"{path}: unknown selection options {sorted(extra)}")
        prefix = f"{assert_name(options['alias'])}: " if "alias" in options else ""
        if key == "__typename" and options.keys() <= {"alias"}:
            return prefix + key
        field = parent.fields.get(key)
        if field is None:
            raise ValueError(f"Unknown field {path}")
        args = []
        for name, value in object_value(options.get("args", {}), path).items():
            arg = field.args.get(name)
            if arg is None:
                raise ValueError(f"{path}: unknown argument {name!r}")
            args.append(f"{name}: {self.value(value, arg.type, f'{path}({name})')}")
        call = "(" + ", ".join(args) + ")" if args else ""
        target = get_named_type(field.type)
        if isinstance(target, (GraphQLObjectType, GraphQLInterfaceType)):
            child = " " + self.selection(target, options.get("select"))
        elif is_leaf_type(target):
            if "select" in options:
                raise ValueError(f"{path}: a leaf field cannot have a selection")
            child = ""
        else:
            raise ValueError(
                f"{path}: abstract result type {target.name} is unsupported"
            )
        return prefix + key + call + child
