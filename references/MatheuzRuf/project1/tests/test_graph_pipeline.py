import csv

from src.graph.build import build_case_graph, export_graph_from_cases
from src.graph.schema import NodeType, Relation
from src.vocab import VocabularyEntry


def _measurement_vocabulary():
    return [
        VocabularyEntry(
            term="lipase",
            aliases=(),
            type="Exam",
        ),
        VocabularyEntry(
            term="solid mass",
            aliases=(),
            type="Finding",
        ),
    ]


def test_build_case_graph_integrates_measurements():
    text = (
        "Lipase was elevated at 850 U/L with reference 10-140 U/L. "
        "A solid mass measured 4 cm."
    )

    nodes, edges = build_case_graph(
        case_id="case_001",
        case_text=text,
        vocabulary=_measurement_vocabulary(),
    )

    node_types = {node.type for node in nodes}
    relations = {edge.relation for edge in edges}
    node_ids = {node.node_id for node in nodes}

    assert NodeType.PATIENT in node_types
    assert NodeType.EXAM_RESULT in node_types
    assert NodeType.MEASUREMENT in node_types
    assert NodeType.VALUE in node_types
    assert NodeType.UNIT in node_types
    assert NodeType.REFERENCE_RANGE in node_types
    assert NodeType.INTERPRETATION in node_types

    assert Relation.HAS_RESULT in relations
    assert Relation.HAS_VALUE in relations
    assert Relation.HAS_UNIT in relations
    assert Relation.HAS_REFERENCE_RANGE in relations
    assert Relation.HAS_LOW in relations
    assert Relation.HAS_HIGH in relations
    assert Relation.HAS_INTERPRETATION in relations
    assert Relation.HAS_SIZE in relations

    assert all(
        edge.source_id in node_ids and edge.target_id in node_ids
        for edge in edges
    )


def test_build_case_graph_links_doses_to_medications_and_treatments():
    vocabulary = [
        VocabularyEntry(
            term="ibuprofen",
            aliases=(),
            type="Medication",
        ),
        VocabularyEntry(
            term="radiotherapy",
            aliases=(),
            type="Treatment",
        ),
    ]
    text = "Ibuprofen 400 mg was prescribed. Radiotherapy 50 Gy was delivered."

    nodes, edges = build_case_graph(
        case_id="case_001",
        case_text=text,
        vocabulary=vocabulary,
    )

    dose_sources = {
        edge.source_id
        for edge in edges
        if edge.relation == Relation.HAS_DOSE
    }
    node_ids = {node.node_id for node in nodes}

    assert dose_sources == {
        "case_001:ibuprofen",
        "case_001:radiotherapy",
    }
    assert all(
        edge.source_id in node_ids and edge.target_id in node_ids
        for edge in edges
    )


def test_export_graph_from_cases_writes_valid_csv_files(tmp_path):
    nodes_path = tmp_path / "nodes.csv"
    edges_path = tmp_path / "edges.csv"
    cases = [
        {
            "case_id": "case_001",
            "case_text": "Lipase was elevated at 850 U/L.",
        }
    ]

    export_graph_from_cases(
        cases,
        _measurement_vocabulary(),
        nodes_path,
        edges_path,
    )

    with nodes_path.open(encoding="utf-8", newline="") as file:
        nodes = list(csv.DictReader(file))

    with edges_path.open(encoding="utf-8", newline="") as file:
        edges = list(csv.DictReader(file))

    assert list(nodes[0]) == ["node_id", "type", "label", "attributes"]
    assert list(edges[0]) == [
        "edge_id",
        "source_id",
        "target_id",
        "relation",
        "attributes",
    ]

    node_ids = {node["node_id"] for node in nodes}
    assert len(node_ids) == len(nodes)
    assert len({edge["edge_id"] for edge in edges}) == len(edges)
    assert all(
        edge["source_id"] in node_ids and edge["target_id"] in node_ids
        for edge in edges
    )
