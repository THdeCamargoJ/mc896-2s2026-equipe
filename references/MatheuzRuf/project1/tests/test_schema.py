from src.graph import Node, NodeType, Edge, Relation


def test_create_node():
    node = Node(
        node_id="P1",
        type=NodeType.PATIENT,
        label="case_example_01",
        attributes="age=52; gender=Male",
    )

    assert node.node_id == "P1"
    assert node.type == NodeType.PATIENT
    assert node.to_dict()["type"] == "Patient"


def test_create_edge():
    edge = Edge(
        edge_id="e1",
        source_id="P1",
        target_id="S1",
        relation=Relation.PRESENTS_WITH,
    )

    assert edge.source_id == "P1"
    assert edge.target_id == "S1"
    assert edge.relation == Relation.PRESENTS_WITH
    assert edge.to_dict()["relation"] == "PRESENTS_WITH"