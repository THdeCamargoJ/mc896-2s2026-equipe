import csv
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from src.visualization.web_server import create_request_handler, list_case_ids


def _write_graph_csvs(tmp_path):
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"

    with nodes_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["node_id", "type", "label", "attributes"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "node_id": "case_1:patient",
                    "type": "Patient",
                    "label": "patient",
                    "attributes": "",
                },
                {
                    "node_id": "case_1:pain",
                    "type": "Symptom",
                    "label": "pain",
                    "attributes": "",
                },
                {
                    "node_id": "case_2:patient",
                    "type": "Patient",
                    "label": "patient",
                    "attributes": "",
                },
            ]
        )

    with edges_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "edge_id",
                "source_id",
                "target_id",
                "relation",
                "attributes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "edge_id": "edge_1",
                "source_id": "case_1:patient",
                "target_id": "case_1:pain",
                "relation": "PRESENTS_WITH",
                "attributes": "",
            }
        )

    return nodes_path, edges_path


def test_list_case_ids_preserves_order(tmp_path):
    nodes_path, _ = _write_graph_csvs(tmp_path)

    assert list_case_ids(nodes_path) == ["case_1", "case_2"]


def test_local_server_returns_page_cases_and_graph(tmp_path):
    nodes_path, edges_path = _write_graph_csvs(tmp_path)
    static_dir = tmp_path / "web"
    static_dir.mkdir()
    (static_dir / "index.html").write_text(
        "<h1>Knowledge Graph</h1>",
        encoding="utf-8",
    )

    handler = create_request_handler(nodes_path, edges_path, static_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()

    try:
        host, port = server.server_address
        with urlopen(f"http://{host}:{port}/") as response:
            page = response.read().decode("utf-8")
        with urlopen(f"http://{host}:{port}/api/cases") as response:
            cases = json.load(response)
        with urlopen(
            f"http://{host}:{port}/api/graph?case_id=case_1"
        ) as response:
            graph = json.load(response)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    assert "Knowledge Graph" in page
    assert cases == {"cases": ["case_1", "case_2"]}
    assert graph["case_id"] == "case_1"
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1
