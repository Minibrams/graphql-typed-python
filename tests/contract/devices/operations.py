from generated import schema

from graphql_typed import var

identity: schema.DeviceFields = {"id": True, "name": True}


def operations():
    return [
        schema.query(
            "DeviceBySerial",
            select={"device": {"args": {"serial": var("serial")}, "select": identity}},
        ),
        schema.query(
            "Compare",
            select={
                "device": [
                    {
                        "alias": "left",
                        "args": {"serial": var("a")},
                        "select": {"id": True, "ports": True},
                    },
                    {
                        "alias": "right",
                        "args": {"serial": var("b")},
                        "select": {"firmware": True},
                    },
                ]
            },
        ),
        schema.query(
            "All",
            select={
                "all": [
                    {"select": {"id": True}},
                    {"select": {"name": True, "__typename": True}},
                ]
            },
        ),
        schema.query("Version", select={"version": {"alias": "release"}}),
    ]
