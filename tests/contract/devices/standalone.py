"""This contract also runs with site packages disabled."""

import asyncio
from collections.abc import Mapping
from importlib.util import find_spec

from generated.client import AsyncClient, Client
from generated.transport import GraphQLResponseError


class Fake:
    def execute(
        self, *, document: str, operation_name: str, variables: Mapping[str, object]
    ) -> object:
        assert operation_name == "DeviceBySerial"
        assert "query DeviceBySerial($serial: String!)" in document
        assert "device(serial: $serial)" in document
        assert variables == {"serial": "R42"}
        return {"data": {"device": {"id": "42", "name": "router"}}}


class AsyncFake:
    async def execute(
        self, *, document: str, operation_name: str, variables: Mapping[str, object]
    ) -> object:
        return Fake().execute(
            document=document, operation_name=operation_name, variables=variables
        )


class Failed:
    def execute(
        self, *, document: str, operation_name: str, variables: Mapping[str, object]
    ) -> object:
        return {
            "data": {"device": None},
            "errors": [{"message": "offline", "path": ["device"]}],
        }


def main():
    assert all(
        find_spec(name) is None for name in ("graphql", "graphql_typed", "httpx")
    )
    expected = {"device": {"id": "42", "name": "router"}}
    assert (
        Client(transport=Fake()).query("DeviceBySerial")(variables={"serial": "R42"})
        == expected
    )
    client = AsyncClient(transport=AsyncFake())
    assert (
        asyncio.run(client.query("DeviceBySerial")(variables={"serial": "R42"}))
        == expected
    )
    try:
        Client(transport=Failed()).query("DeviceBySerial")(variables={"serial": "R42"})
    except GraphQLResponseError as exc:
        assert str(exc) == "offline"
        assert exc.errors == [{"message": "offline", "path": ["device"]}]
        assert exc.data == {"device": None}
    else:
        raise AssertionError("expected a GraphQLResponseError")
