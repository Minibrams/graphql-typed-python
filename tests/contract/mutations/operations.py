from generated import schema

from graphql_typed import var


def operations():
    return [
        schema.mutation(
            "Update",
            select={
                "update": {
                    "args": {"id": var("id"), "patch": var("patch")},
                    "select": {"mode": True, "serial": True},
                }
            },
        ),
        schema.mutation(
            "SetLabels",
            select={
                "update": {
                    "args": {
                        "id": 7,
                        "patch": {
                            "mode": "ONLINE",
                            "labels": [var("label")],
                            "serial": var("serial"),
                        },
                    },
                    "select": {"mode": True},
                }
            },
        ),
        schema.query(
            "Lookup",
            select={
                "lookup": {"args": {"mode": var("mode")}, "select": {"mode": True}}
            },
        ),
    ]
