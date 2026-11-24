"""Transport contracts and execution shared by the generated clients."""

from collections.abc import Mapping
from typing import Any, Protocol


class Transport(Protocol):
    """Send requests for a sync client, for example ``Client(transport=fake)`` in a test."""

    def execute(
        self, *, document: str, operation_name: str, variables: Mapping[str, object]
    ) -> object:
        """Return the decoded GraphQL envelope, for example ``{"data": {"version": "1"}}``."""
        ...


class AsyncTransport(Protocol):
    """Send requests for an async client, for example ``AsyncClient(transport=session)``."""

    async def execute(
        self, *, document: str, operation_name: str, variables: Mapping[str, object]
    ) -> object:
        """Return the decoded GraphQL envelope, for example ``{"data": {"version": "1"}}``."""
        ...


class GraphQLResponseError(Exception):
    """Raised for a GraphQL error response, including one with partial data.

    In ``except GraphQLResponseError as exc:``, inspect ``exc.errors`` and ``exc.data``.
    """

    def __init__(self, errors: list[Any], data: object) -> None:
        self.errors = errors
        self.data = data
        super().__init__(
            "; ".join(
                str(e.get("message", e)) if isinstance(e, dict) else str(e)
                for e in errors
            )
        )


def _data(response: object) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise TypeError("Expected a GraphQL response object")
    if "errors" in response:
        errors = response["errors"]
        if not isinstance(errors, list) or not errors:
            raise ValueError("Expected a nonempty list of GraphQL errors")
        raise GraphQLResponseError(errors, response.get("data"))
    data = response.get("data")
    if not isinstance(data, dict):
        raise TypeError("Expected a GraphQL data object")
    return data


def _payload(
    document: str, name: str, variables: Mapping[str, object]
) -> dict[str, object]:
    return {"query": document, "operationName": name, "variables": dict(variables)}


class SyncExecutor:
    def __init__(
        self, endpoint: str | None = None, *, transport: Transport | None = None
    ):
        if transport is None and not endpoint:
            raise ValueError("Supply an endpoint or a transport")
        self._endpoint = endpoint
        self._transport = transport

    def _bind(self, name: str, documents: dict[str, str]):
        document = documents[name]

        def run(*, variables: Mapping[str, object] | None = None):
            """Execute the operation. Use ``run()`` or pass its variables with ``run(variables=values)``."""
            values = variables if variables is not None else {}
            if self._transport is not None:
                response = self._transport.execute(
                    document=document, operation_name=name, variables=values
                )
            else:
                import httpx

                assert self._endpoint is not None
                result = httpx.post(
                    self._endpoint, json=_payload(document, name, values)
                )
                response = _http_response(result)
            return _data(response)

        return run


def _http_response(result: Any) -> object:
    if not result.is_success:
        try:
            body = result.json()
        except ValueError:
            result.raise_for_status()
            raise
        if isinstance(body, dict) and body.get("errors"):
            return body
        result.raise_for_status()
    return result.json()


class AsyncExecutor:
    def __init__(
        self, endpoint: str | None = None, *, transport: AsyncTransport | None = None
    ):
        if transport is None and not endpoint:
            raise ValueError("Supply an endpoint or a transport")
        self._endpoint = endpoint
        self._transport = transport

    def _bind(self, name: str, documents: dict[str, str]):
        document = documents[name]

        async def run(*, variables: Mapping[str, object] | None = None):
            """Execute the operation. Use ``await run()`` or ``await run(variables=values)``."""
            values = variables if variables is not None else {}
            if self._transport is not None:
                response = await self._transport.execute(
                    document=document, operation_name=name, variables=values
                )
            else:
                import httpx

                assert self._endpoint is not None
                async with httpx.AsyncClient() as client:
                    result = await client.post(
                        self._endpoint, json=_payload(document, name, values)
                    )
                response = _http_response(result)
            return _data(response)

        return run
