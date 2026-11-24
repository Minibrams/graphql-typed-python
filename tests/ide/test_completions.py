from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def ide_workspace(devices: Path) -> Path:
    return devices


@pytest.mark.parametrize(
    ("source", "keys"),
    [
        ("schema.query('Q', select={'device': {'args': {'<CURSOR>'}}})", {"serial"}),
        (
            "schema.query('Q', select={'device': [{'select': {'<CURSOR>'}}]})",
            {"id", "name", "ports"},
        ),
        ("client.query('<CURSOR>')", {"DeviceBySerial", "Compare", "All"}),
        ("client.query('DeviceBySerial')(variables={'<CURSOR>'})", {"serial"}),
        (
            "data = client.query('Compare')(variables={'a':'a','b':'b'})\ndata['<CURSOR>']",
            {"left", "right"},
        ),
        (
            "data = client.query('DeviceBySerial')(variables={'serial':'a'})\nif (device := data['device']) is not None:\n    device['<CURSOR>']",
            {"id", "name"},
        ),
    ],
)
def test_completions(ty_server, source: str, keys: set[str]):
    labels = ty_server.completion_labels(
        "from generated import schema\nfrom generated.client import Client\nclient = Client('https://example.test')\n"
        + source
    )
    assert keys <= labels
    if keys == {"id", "name"}:
        assert "firmware" not in labels
