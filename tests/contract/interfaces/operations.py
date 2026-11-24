from generated import schema

peers: schema.InterfaceFields = {
    "name": True,
    "__typename": True,
    "... on InterfaceVirtual": {
        "parent_interface": {"select": {"name": True, "__typename": {"alias": "kind"}}}
    },
}


def operations():
    return [
        schema.query(
            "Peers",
            select={
                "device": {
                    "select": {
                        "peer": {"select": {"interfaces": {"select": peers}}},
                    }
                }
            },
        ),
        schema.query(
            "Names",
            select={"device": {"select": {"interfaces": {"select": {"name": True}}}}},
        ),
    ]
