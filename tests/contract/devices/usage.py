from typing import Literal, assert_type

from generated.client import AsyncClient, Client
from generated.types import DeviceBySerialData, DeviceBySerialVariables


async def check(client: Client, async_client: AsyncClient) -> None:
    variables: DeviceBySerialVariables = {"serial": "R42"}
    assert_type(
        await async_client.query("DeviceBySerial")(variables=variables),
        DeviceBySerialData,
    )
    device = client.query("DeviceBySerial")(variables={"serial": "R42"})["device"]
    if device is not None:
        assert_type(device["name"], str)
    compared = await async_client.query("Compare")(variables={"a": "one", "b": "two"})
    if (left := compared["left"]) is not None:
        assert_type(left["id"], str)
        assert_type(left["ports"], list[list[int | None]])
    if (right := compared["right"]) is not None:
        assert_type(right["firmware"], str | None)
    for item in client.query("All")()["all"]:
        assert_type(item["id"], str)
        assert_type(item["name"], str)
        assert_type(item["__typename"], Literal["Device"])
    assert_type(client.query("Version")()["release"], str)
