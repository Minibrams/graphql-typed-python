from typing import Literal, assert_type

from generated.client import Client
from generated.types import PeersData_device_peer_interfaces as Peer
from generated.types import PeersData_device_peer_interfaces_parent_interface as Parent


def check(client: Client):
    device = client.query("Peers")()["device"]["peer"]
    if device is None:
        return
    peers = assert_type(device["interfaces"], list[Peer | None] | None)
    if peers is None:
        return
    for peer in peers:
        if peer is None:
            continue
        assert_type(peer["name"], str)
        if peer["__typename"] == "InterfaceVirtual":
            parent = assert_type(peer["parent_interface"], Parent | None)
            if parent is not None:
                assert_type(parent["name"], str)
                assert_type(
                    parent["kind"], Literal["InterfacePhysical", "InterfaceVirtual"]
                )
                parent["parent_interface"]  # ty: ignore[invalid-typed-dict-key]
        else:
            assert_type(peer["__typename"], Literal["InterfacePhysical"])
            peer["parent_interface"]  # ty: ignore[invalid-typed-dict-key]

    for item in client.query("Names")()["device"]["interfaces"] or []:
        if item is not None:
            assert_type(item["name"], str)
            item["__typename"]  # ty: ignore[invalid-typed-dict-key]
