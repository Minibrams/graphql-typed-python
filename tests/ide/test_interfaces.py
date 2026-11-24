from pathlib import Path

import pytest

from tests.conftest import build_contract


@pytest.fixture(scope="module")
def ide_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_contract(tmp_path_factory.mktemp("interfaces"), "interfaces")


def test_fragment_completions(ty_server):
    def complete(selection):
        return ty_server.completion_labels(
            "from generated import schema\n"
            "schema.query('Q', select={'device': {'select': {'interfaces': {'select': {"
            + selection
            + "}}}}})"
        )

    keys = complete("'<CURSOR>'")
    assert {
        "... on InterfaceVirtual",
        "... on InterfacePhysical",
        "__typename",
        "name",
    } <= keys
    assert "parent_interface" not in keys
    assert "parent_interface" in complete("'... on InterfaceVirtual': {'<CURSOR>'}")
    assert "parent_interface" not in complete(
        "'... on InterfacePhysical': {'<CURSOR>'}"
    )
