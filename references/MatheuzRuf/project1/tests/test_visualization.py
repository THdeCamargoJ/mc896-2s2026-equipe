import csv

from src.visualization import load_case_graph


def _write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def test_load_case_graph_filters_nodes_and_edges(tmp_path):
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"

    _write_csv(
        nodes_path,
        ["node_id", "type", "label", "attributes"],
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
        ],
    )
    _write_csv(
        edges_path,
        ["edge_id", "source_id", "target_id", "relation", "attributes"],
        [
            {
                "edge_id": "edge_1",
                "source_id": "case_1:patient",
                "target_id": "case_1:pain",
                "relation": "PRESENTS_WITH",
                "attributes": "",
            }
        ],
    )

    case_id, nodes, edges = load_case_graph(
        nodes_path,
        edges_path,
        case_id="case_1",
    )

    assert case_id == "case_1"
    assert len(nodes) == 2
    assert len(edges) == 1
    assert {node["type"] for node in nodes} == {"Patient", "Symptom"}
    assert edges[0]["relation"] == "PRESENTS_WITH"


def test_load_case_graph_uses_first_case_by_default(tmp_path):
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"

    _write_csv(
        nodes_path,
        ["node_id", "type", "label", "attributes"],
        [
            {
                "node_id": "case_1:patient",
                "type": "Patient",
                "label": "patient",
                "attributes": "",
            }
        ],
    )
    _write_csv(
        edges_path,
        ["edge_id", "source_id", "target_id", "relation", "attributes"],
        [],
    )

    case_id, nodes, edges = load_case_graph(nodes_path, edges_path)

    assert case_id == "case_1"
    assert len(nodes) == 1
    assert edges == []
