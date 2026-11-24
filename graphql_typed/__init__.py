"""Build named operations with the types in your generated schema module."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Variable:
    name: str


def var(name: str) -> Variable:
    return Variable(name)


@dataclass(frozen=True)
class Operation:
    kind: Literal["query", "mutation"]
    name: str
    select: object
