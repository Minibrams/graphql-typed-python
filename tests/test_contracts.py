import subprocess
from pathlib import Path

import pytest

from tests.conftest import CONTRACTS, build_contract


@pytest.mark.parametrize(
    "case", sorted(path.name for path in CONTRACTS.iterdir() if path.is_dir())
)
def test_generated_and_usage_types(tmp_path: Path, case: str):
    build_contract(tmp_path, case)
    run = subprocess.run(
        [
            "ty",
            "check",
            ".",
            "--python-version",
            "3.12",
            "--error",
            "unused-ignore-comment",
        ],
        check=False,
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_invalid_calls(devices: Path):
    source = devices / "mistakes.py"
    source.write_text("""
from generated import schema
from generated.client import Client
client = Client("http://example.test")
schema.query("Q", select={"device":[{"args":{"serial":"R42"}, "select":{"typo":True}}]})
client.query("Missing")()
client.query("DeviceBySerial")(variables={})
client.query("DeviceBySerial")(variables={"serial": 1})
result = client.query("DeviceBySerial")(variables={"serial":"R42"})
if (device := result["device"]) is not None:
    print(device["firmware"])
""")
    run = subprocess.run(
        ["ty", "check", source.name, "--output-format", "concise"],
        check=False,
        cwd=devices,
        text=True,
        capture_output=True,
    )
    assert run.returncode == 1
    for line in (5, 6, 7, 8, 11):
        assert f"mistakes.py:{line}:" in run.stdout, run.stdout
