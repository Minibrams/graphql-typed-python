import argparse
from pathlib import Path

from graphql import GraphQLError

from graphql_typed.generator import generate


def main() -> None:
    """Run the CLI, for example ``graphql-typed generate schema.graphql --out generated``."""
    parser = argparse.ArgumentParser(prog="graphql-typed")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser(
        "generate", help="Generate schema types and typed operation clients"
    )
    command.add_argument(
        "source", help="SDL file, introspection JSON file, or endpoint URL"
    )
    command.add_argument(
        "--out", type=Path, required=True, help="Generated package directory"
    )
    command.add_argument(
        "--operations", metavar="MODULE:FUNCTION", help="Named operation factory"
    )
    command.add_argument(
        "--no-ssl",
        action="store_true",
        help="Disable TLS verification for schema fetching",
    )
    args = parser.parse_args()
    try:
        generate(
            args.source,
            args.out,
            operations=args.operations,
            verify_ssl=not args.no_ssl,
        )
    except (OSError, TypeError, ValueError, GraphQLError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
