from generated import schema

from graphql_typed import var


def operations():
    return [
        schema.query(
            "Tree",
            select={
                "from": {
                    "args": {
                        "where": {"and": [{"class": var("term")}]},
                        "second": var("term"),
                    },
                    "select": {
                        "class": True,
                        "parent": {"select": {"class": {"alias": "else"}}},
                    },
                }
            },
        )
    ]
