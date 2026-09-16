from src.graph.build import build_case_graph
from src.graph.schema import NodeType, Relation
from src.vocab import VocabularyEntry


def test_build_case_graph_creates_patient_and_patient_relations():
    vocabulary = [
        VocabularyEntry(
            term="abdominal pain",
            aliases=(),
            type="Symptom",
        ),
        VocabularyEntry(
            term="computed tomography",
            aliases=("CT scan",),
            type="Exam",
        ),
        VocabularyEntry(
            term="ibuprofen",
            aliases=(),
            type="Medication",
        ),
    ]

    nodes, edges = build_case_graph(
        case_id="case_001",
        case_text="Patient with abdominal pain underwent a CT scan and received ibuprofen.",
        vocabulary=vocabulary,
    )

    nodes_by_id = {node.node_id: node for node in nodes}
    relations = {
        (edge.source_id, edge.target_id, edge.relation)
        for edge in edges
    }

    assert nodes_by_id["case_001:patient"].type == NodeType.PATIENT
    assert (
        "case_001:patient",
        "case_001:abdominal pain",
        Relation.PRESENTS_WITH,
    ) in relations
    assert (
        "case_001:patient",
        "case_001:computed tomography",
        Relation.UNDERWENT_EXAM,
    ) in relations
    assert (
        "case_001:patient",
        "case_001:ibuprofen",
        Relation.TREATED_BY,
    ) in relations

    node_ids = set(nodes_by_id)
    assert all(
        edge.source_id in node_ids and edge.target_id in node_ids
        for edge in edges
    )
