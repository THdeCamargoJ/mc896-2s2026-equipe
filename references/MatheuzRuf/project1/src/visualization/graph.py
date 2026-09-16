import csv
from pathlib import Path


NODE_COLORS = {
    "Patient": "#e74c3c",
    "Diagnosis": "#8e44ad",
    "Symptom": "#f39c12",
    "Exam": "#2980b9",
    "ExamResult": "#3498db",
    "Finding": "#16a085",
    "Treatment": "#27ae60",
    "Medication": "#2ecc71",
    "Outcome": "#1abc9c",
    "Measurement": "#7f8c8d",
    "Value": "#95a5a6",
    "Unit": "#bdc3c7",
    "ReferenceRange": "#34495e",
    "Interpretation": "#d35400",
    "AnatomicalSite": "#c0392b",
    "Status": "#9b59b6",
    "Course": "#f1c40f",
}

DEFAULT_NODE_COLOR = "#cccccc"


def _read_csv(path: str | Path) -> list[dict]:
    path = Path(path)
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def load_case_graph(
    nodes_path: str | Path,
    edges_path: str | Path,
    case_id: str | None = None,
) -> tuple[str, list[dict], list[dict]]:
    """Carrega dos CSVs somente os nos e arestas de um caso."""

    all_nodes = _read_csv(nodes_path)
    all_edges = _read_csv(edges_path)

    if not all_nodes:
        raise ValueError("nodes.csv is empty")

    if case_id is None:
        case_id = all_nodes[0]["node_id"].split(":", 1)[0]

    prefix = f"{case_id}:"
    nodes = [
        node
        for node in all_nodes
        if node["node_id"].startswith(prefix)
    ]

    if not nodes:
        raise ValueError(f"case_id not found: {case_id}")

    node_ids = {node["node_id"] for node in nodes}
    edges = [
        edge
        for edge in all_edges
        if edge["source_id"] in node_ids and edge["target_id"] in node_ids
    ]

    return case_id, nodes, edges


def visualize_case(
    nodes_path: str | Path,
    edges_path: str | Path,
    output_path: str | Path,
    case_id: str | None = None,
) -> str:
    """Gera uma visualizacao basica de um caso e salva em PNG."""

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import networkx as nx
        from matplotlib.patches import Patch
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Install the project dependencies with: pip install -r requirements.txt"
        ) from error

    case_id, nodes, edges = load_case_graph(
        nodes_path,
        edges_path,
        case_id,
    )

    graph = nx.DiGraph()
    for node in nodes:
        graph.add_node(
            node["node_id"],
            label=node["label"],
            type=node["type"],
        )

    for edge in edges:
        graph.add_edge(
            edge["source_id"],
            edge["target_id"],
            relation=edge["relation"],
        )

    figure = plt.figure(figsize=(18, 12))
    positions = nx.spring_layout(graph, seed=42)
    colors = [
        NODE_COLORS.get(graph.nodes[node]["type"], DEFAULT_NODE_COLOR)
        for node in graph.nodes
    ]
    labels = {
        node: graph.nodes[node]["label"]
        for node in graph.nodes
    }
    edge_labels = {
        (source, target): data["relation"]
        for source, target, data in graph.edges(data=True)
    }

    nx.draw_networkx_nodes(
        graph,
        positions,
        node_color=colors,
        node_size=1800,
        alpha=0.9,
    )
    nx.draw_networkx_edges(
        graph,
        positions,
        arrows=True,
        arrowsize=15,
        edge_color="#777777",
    )
    nx.draw_networkx_labels(
        graph,
        positions,
        labels=labels,
        font_size=7,
    )
    nx.draw_networkx_edge_labels(
        graph,
        positions,
        edge_labels=edge_labels,
        font_size=5,
    )

    present_types = sorted({node["type"] for node in nodes})
    legend = [
        Patch(
            color=NODE_COLORS.get(node_type, DEFAULT_NODE_COLOR),
            label=node_type,
        )
        for node_type in present_types
    ]
    plt.legend(handles=legend, loc="upper left", fontsize=8)
    plt.title(f"Knowledge Graph - {case_id}")
    plt.axis("off")
    plt.tight_layout()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)

    return case_id
