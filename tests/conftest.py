import shutil
import subprocess
from pathlib import Path

import pytest

CONTRACTS = Path(__file__).parent / "contract"


def build_contract(workspace: Path, case: str) -> Path:
    shutil.copytree(CONTRACTS / case, workspace, dirs_exist_ok=True)
    run = subprocess.run(
        [
            "graphql-typed",
            "generate",
            "schema.graphql",
            "--out",
            "generated",
            "--operations",
            "operations:operations",
        ],
        check=False,
        cwd=workspace,
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, run.stderr
    return workspace


@pytest.fixture(scope="session")
def devices(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_contract(tmp_path_factory.mktemp("devices"), "devices")
