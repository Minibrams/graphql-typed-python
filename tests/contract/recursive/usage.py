from typing import assert_type

from generated.client import Client


def check(client: Client):
    node = client.query("Tree")(variables={"term": "region"})["from"]
    assert_type(node["class"], str)
    if (parent := node["parent"]) is not None:
        assert_type(parent["else"], str)
