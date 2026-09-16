import csv
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.visualization.graph import load_case_graph


def list_case_ids(nodes_path: str | Path) -> list[str]:
    """Lista os case_ids na mesma ordem em que aparecem em nodes.csv."""

    case_ids = []
    seen = set()

    with Path(nodes_path).open("r", encoding="utf-8", newline="") as file:
        for node in csv.DictReader(file):
            case_id = node["node_id"].split(":", 1)[0]
            if case_id not in seen:
                seen.add(case_id)
                case_ids.append(case_id)

    return case_ids


def create_request_handler(
    nodes_path: str | Path,
    edges_path: str | Path,
    static_dir: str | Path,
):
    nodes_path = Path(nodes_path)
    edges_path = Path(edges_path)
    static_dir = Path(static_dir)

    class GraphRequestHandler(BaseHTTPRequestHandler):
        def _send_json(self, data, status=200):
            content = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _send_static(self, filename, content_type):
            path = static_dir / filename
            if not path.exists():
                self.send_error(404)
                return

            content = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            request = urlparse(self.path)

            if request.path == "/api/cases":
                self._send_json({"cases": list_case_ids(nodes_path)})
                return

            if request.path == "/api/graph":
                query = parse_qs(request.query)
                case_id = query.get("case_id", [None])[0]

                try:
                    selected_case, nodes, edges = load_case_graph(
                        nodes_path,
                        edges_path,
                        case_id,
                    )
                except ValueError as error:
                    self._send_json({"error": str(error)}, status=404)
                    return

                self._send_json(
                    {
                        "case_id": selected_case,
                        "nodes": nodes,
                        "edges": edges,
                    }
                )
                return

            static_files = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            }
            static_file = static_files.get(request.path)
            if static_file:
                self._send_static(*static_file)
                return

            self.send_error(404)

        def log_message(self, format, *args):
            return

    return GraphRequestHandler


def serve_graph_interface(
    nodes_path: str | Path,
    edges_path: str | Path,
    static_dir: str | Path,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    """Executa a interface local ate o usuario interromper o processo."""

    handler = create_request_handler(nodes_path, edges_path, static_dir)
    server = ThreadingHTTPServer((host, port), handler)

    print(f"Graph interface running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping graph interface.")
    finally:
        server.server_close()


__all__ = [
    "list_case_ids",
    "create_request_handler",
    "serve_graph_interface",
]
