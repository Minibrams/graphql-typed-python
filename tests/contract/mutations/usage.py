from typing import Any, Literal, assert_type

from generated.client import AsyncClient, Client
from generated.types import PatchInput


async def check(client: Client, async_client: AsyncClient) -> None:
    patch: PatchInput = {"mode": "OFFLINE", "labels": []}
    changed = client.mutation("Update")(variables={"id": 1, "patch": patch})
    assert_type(changed["update"]["mode"], Literal["ONLINE", "OFFLINE"])
    assert_type(changed["update"]["serial"], Any | None)
    await async_client.mutation("SetLabels")(
        variables={"label": "edge", "serial": {"code": 17}}
    )
    result = await async_client.query("Lookup")()
    for device in result["lookup"]:
        if device is not None:
            assert_type(device["mode"], Literal["ONLINE", "OFFLINE"])
    client.query("Lookup")(variables={"mode": None})
