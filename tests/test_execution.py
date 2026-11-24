import json
import ssl
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from graphql import build_schema, graphql_sync

from graphql_typed.generator import generate
from tests.conftest import CONTRACTS


@contextmanager
def endpoint(
    case: str, tls: ssl.SSLContext | None = None
) -> Generator[str, None, None]:
    schema = build_schema((CONTRACTS / case / "schema.graphql").read_text())

    def device(_info, serial):
        return {"id": 1, "name": serial, "ports": [[1, None]], "firmware": None}

    def update(_info, id, patch):
        return {"mode": patch["mode"], "serial": patch.get("serial")}

    root = {"device": device, "all": [device(None, "a")], "update": update}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            result = graphql_sync(
                schema,
                payload["query"],
                root_value=root,
                variable_values=payload.get("variables"),
                operation_name=payload.get("operationName"),
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result.formatted).encode())

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        if tls:
            server.socket = tls.wrap_socket(server.socket, server_side=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"{'https' if tls else 'http'}://127.0.0.1:{server.server_port}/graphql"
        finally:
            server.shutdown()
            thread.join()


def test_http_introspection_and_execution(tmp_path: Path):
    (tmp_path / "operations.py").write_bytes(
        (CONTRACTS / "mutations/operations.py").read_bytes()
    )
    with endpoint("mutations") as url:
        generate(url, tmp_path / "generated", operations="operations:operations")
        script = tmp_path / "execute.py"
        script.write_bytes((CONTRACTS / "mutations/execute.py").read_bytes())
        subprocess.run([sys.executable, script, url], cwd=tmp_path, check=True)


def test_cli_tls_option(tmp_path: Path):
    pem = str(tmp_path / "cert.pem")
    key = str(tmp_path / "key.pem")
    subprocess.run(
        [
            "openssl",
            "req",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-x509",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-keyout",
            key,
            "-out",
            pem,
        ],
        check=True,
        capture_output=True,
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(pem, key)
    with endpoint("devices", context) as url:
        command = ["graphql-typed", "generate", url, "--out", "generated"]
        failed = subprocess.run(
            command, check=False, cwd=tmp_path, capture_output=True, text=True
        )
        assert failed.returncode and "CERTIFICATE_VERIFY_FAILED" in failed.stderr
        subprocess.run([*command, "--no-ssl"], cwd=tmp_path, check=True)
    assert (tmp_path / "generated/schema.py").is_file()


def test_standalone_clients(devices: Path):
    subprocess.run(
        [
            sys.executable,
            "-IS",
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); from standalone import main; main()",
            str(devices),
        ],
        check=True,
    )


def test_aliased_and_merged_responses(devices: Path):
    with endpoint("devices") as url:
        subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
from generated.client import Client
client = Client(sys.argv[1])
assert client.query("Compare")(variables={"a":"a", "b":"b"}) == {
    "left":{"id":"1","ports":[[1,None]]}, "right":{"firmware":None}
}
assert client.query("All")() == {"all":[{"id":"1","name":"a","__typename":"Device"}]}
""",
                url,
            ],
            cwd=devices,
            check=True,
        )
