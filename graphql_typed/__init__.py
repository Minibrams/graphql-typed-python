"""Build named operations with the types in your generated schema module."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Variable:
    """A reference to a GraphQL variable, such as ``var("serial")`` in a field argument."""

    name: str


def var(name: str) -> Variable:
    """Use a caller-supplied variable in a selection, as in ``{"args": {"id": var("id")}}``."""
    return Variable(name)


@dataclass(frozen=True)
class Operation:
    """A named selection returned by an operation factory.

    For example, return ``[schema.query("RootType", select={"__typename": True})]``.
    """

    kind: Literal["query", "mutation"]
    name: str
    select: object
