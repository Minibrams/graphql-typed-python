# graphql-typed-python

Build GraphQL operations with Python dictionary literals and get static types for both the request and the selected response fields. Generation has two passes. The schema supplies completions while you write your operations. Each named operation then supplies the variables and return type for the generated client.

## Quick start

Use Python 3.12 or newer. Install the generator in your development environment. Applications using the default HTTP transport also need `httpx`.

```sh
uv add --dev graphql-typed-python
uv add httpx
```

Given a `schema.graphql` file:

```graphql
type Query { device(serial: String!): Device }
type Device { id: ID!, name: String!, firmware: String }
```

Generate the authoring types:

```sh
uv run graphql-typed generate schema.graphql --out generated
```

Write `operations.py` alongside the generated package:

```python
from generated import schema
from graphql_typed import Operation, var

identity: schema.DeviceFields = {"id": True, "name": True}


def operations() -> list[Operation]:
    return [
        schema.query(
            "DeviceBySerial",
            select={
                "device": {
                    "args": {"serial": var("serial")},
                    "select": identity,
                },
            },
        )
    ]
```

Generate the client. This command also works on a fresh checkout. The generator evaluates the factory against the newly generated schema types before writing its outputs.

```sh
uv run graphql-typed generate schema.graphql --out generated --operations operations:operations
```

Use the same name to execute the operation:

```python
from generated.client import AsyncClient


async def device_name(client: AsyncClient, serial: str) -> str | None:
    data = await client.query("DeviceBySerial")(variables={"serial": serial})
    if (device := data["device"]) is not None:
        return device["name"]
    return None
```

Construct a client with `AsyncClient("https://example.test/graphql")`. The sync equivalent is `Client(endpoint).query("DeviceBySerial")(variables={"serial": "R42"})`. Completion follows the selected fields. Accessing `device["firmware"]` in this example is a type error.

## Selections and variables

- Use `True` for a leaf field, `args` for field arguments, and `select` for nested fields. Object selections must contain at least one field.
- Use either a single selection or a list for each field. An alias becomes the key in the result. For example, `"name": [{"alias": "label"}]` yields `device["label"]`. Give distinct aliases to fields with different arguments.
- Use `var("name")` at an argument, input object field, or list item. The first use determines its GraphQL type. Further uses must have exactly the same type, including nullability and list markers. Custom scalars retain their GraphQL names and use Python `Any`.
- Input objects are dictionaries and enum values are string literals. Nullable variables can be omitted or set to `None`. A selected nullable response field has a required key whose value can be `None`.
- Use `schema.mutation(...)` and `client.mutation("Name")(...)` for mutations. Operations without variables are called as `client.query("Name")()`.
- Queries and mutations support object and interface results. Union results, subscriptions, and directives on selections are outside the current scope.

### Interface selections

Select shared fields directly. Add a key such as `"... on InterfaceVirtual"` for fields specific to a concrete implementation. The generated selection type provides completions for each fragment key and for the fields inside it.

```python
peers: schema.InterfaceFields = {
    "name": True,
    "__typename": True,
    "... on InterfaceVirtual": {
        "parent_interface": {"select": {"name": True}},
    },
}
```

Use `peers` as the `select` value of an interface-valued field. Given an item from that result, `ty` can narrow on the selected `__typename`:

```python
label = peer["name"]
if peer["__typename"] == "InterfaceVirtual":
    parent = peer["parent_interface"]
    if parent is not None:
        label = parent["name"]
```

The physical branch has only `name` and `__typename`. Selecting `__typename` is optional. If you alias it, use the alias for narrowing. Nested relationships retain their selected fields and schema nullability.

## Schema sources and output

The source can be an SDL file, a local introspection JSON document (raw or wrapped in `data`), or an HTTP(S) GraphQL endpoint. Endpoint generation issues an unauthenticated introspection request. Add `--no-ssl` to disable certificate verification for that request.

```sh
uv run graphql-typed generate https://example.test/graphql --out generated --operations operations:operations
```

For programmatic use, import `generate` from `graphql_typed.generator`. It accepts `source`, `out`, and the optional keyword arguments `operations` and `verify_ssl`. The factory reference uses `module:function` and the module must be importable.

| Generated module | Contents |
| --- | --- |
| `generated.schema` | Authoring types and operation builders. Used during development and generation. |
| `generated.client` | Sync and async clients with operation-name overloads. |
| `generated.types` | Input objects, per-operation variables, and response dictionaries. |
| `generated.transport` | Structural transport protocols and `GraphQLResponseError`. |

## Transports and errors

The default transport posts GraphQL JSON using `httpx`. To supply a transport, implement the following method and pass the object to the client. An async transport provides an `async def execute` method with the same parameters.

```python
from collections.abc import Mapping
from generated.client import Client


class FakeTransport:
    def execute(
        self, *, document: str, operation_name: str, variables: Mapping[str, object]
    ) -> object:
        return {"data": {"device": {"id": "42", "name": "router"}}}


client = Client(transport=FakeTransport())
```

A transport returns the decoded GraphQL response envelope. The client returns its `data` on success. When the envelope contains errors, it raises `generated.transport.GraphQLResponseError` with `.errors` and `.data`, including any partial result. Consumers using a custom transport can run the generated client with the Python standard library alone.

## Development

```sh
uv sync --locked
prek install
prek run --all-files
uv build
```

Small schemas, operation factories, and `typing.assert_type` examples live in `tests/contract/`. The tests generate clients in temporary packages, check them with `ty`, exercise editor completions via its language server, and execute queries through custom transports and a local GraphQL HTTP server. The TLS test uses the `openssl` command. `just check` runs the same formatting, typing, and test checks used in CI.

The release workflow builds and checks distributions on pushes to the `releases` branch and publishes using PyPI trusted publishing. `just release` runs local release checks and pushes the version bump.
