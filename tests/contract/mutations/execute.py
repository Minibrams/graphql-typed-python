import asyncio
import sys

from generated.client import AsyncClient, Client

url = sys.argv[1]
result = Client(url).mutation("Update")(
    variables={
        "id": "42",
        "patch": {"mode": "OFFLINE", "labels": [], "serial": {"tag": 1}},
    }
)
assert result == {"update": {"mode": "OFFLINE", "serial": {"tag": 1}}}
changed = asyncio.run(
    AsyncClient(url).mutation("SetLabels")(variables={"label": "edge"})
)
assert changed == {"update": {"mode": "ONLINE"}}
