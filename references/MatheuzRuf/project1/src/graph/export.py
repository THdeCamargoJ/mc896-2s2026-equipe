import csv
from pathlib import Path

from src.graph.schema import Node, Edge


NODE_COLUMNS = [
    "node_id",
    "type",
    "label",
    "attributes",
]

EDGE_COLUMNS = [
    "edge_id",
    "source_id",
    "target_id",
    "relation",
    "attributes",
]


def save_nodes(nodes: list[Node], path: str | Path) -> None:
    """Salva uma lista de nodes no formato nodes.csv."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=NODE_COLUMNS)
        writer.writeheader()

        for node in nodes:
            writer.writerow(node.to_dict())


def save_edges(edges: list[Edge], path: str | Path) -> None:
    """Salva uma lista de edges no formato edges.csv."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=EDGE_COLUMNS)
        writer.writeheader()

        for edge in edges:
            writer.writerow(edge.to_dict())