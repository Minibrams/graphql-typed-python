import json
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

from graphql import (
    GraphQLSchema,
    assert_valid_schema,
    build_client_schema,
    build_schema,
    get_introspection_query,
)


def load_schema(source: str, *, verify_ssl: bool = True) -> GraphQLSchema:
    if source.startswith(("http://", "https://")):
        request = Request(
            source,
            data=json.dumps({"query": get_introspection_query()}).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        context = None if verify_ssl else ssl._create_unverified_context()
        with urlopen(request, timeout=30, context=context) as response:
            document = json.load(response)
    else:
        path = Path(source)
        content = path.read_text(encoding="utf-8")
        if path.suffix.lower() != ".json" and not content.lstrip().startswith("{"):
            schema = build_schema(content)
            assert_valid_schema(schema)
            return schema
        document = json.loads(content)
    if not isinstance(document, dict):
        raise TypeError("Expected an introspection JSON object")
    if document.get("errors"):
        raise ValueError(f"Schema introspection failed: {document['errors']}")
    schema = build_client_schema(document.get("data", document))
    assert_valid_schema(schema)
    return schema
