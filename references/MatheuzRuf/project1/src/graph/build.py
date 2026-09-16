from pathlib import Path

from src.Regex.measurement_adapter import (
    DURATION_UNITS,
    SIZE_UNITS,
    extract_structured_measurements,
    is_dose_unit,
)
from src.extraction import Entity, extract_entities
from src.extraction.relations import _dedupe_edges, extract_case_relations
from src.graph.export import save_edges, save_nodes
from src.graph.schema import Edge, Node, NodeType, Relation
from src.vocab import load_vocabulary


ENTITY_FILES = [
    "diseases.csv",
    "symptoms.csv",
    "exams.csv",
    "treatments.csv",
    "medications.csv",
    "anatomical_sites.csv",
    "findings.csv",
    "statuses.csv",
    "courses.csv",
    "outcomes.csv",
]

def _node_id(case_id: str, label: str) -> str:
    clean = " ".join(label.strip().lower().split())
    return f"{case_id}:{clean}"


def _entity_to_node(case_id: str, entity) -> Node:
    return Node(
        node_id=_node_id(case_id, entity.label),
        type=NodeType(entity.type),
        label=entity.label,
        attributes=f"source={entity.source};code={entity.code}",
    )


def _edge(source_id: str, target_id: str, relation: Relation) -> Edge:
    return Edge(
        edge_id=f"{source_id}->{target_id}:{relation.value}",
        source_id=source_id,
        target_id=target_id,
        relation=relation,
        attributes="",
    )


def _build_measurement_graph(
    case_id: str,
    measurements: list,
) -> tuple[list[Node], list[Edge]]:
    nodes: list[Node] = []
    edges: list[Edge] = []

    for index, measurement in enumerate(measurements, start=1):
        if measurement.entity and measurement.entity.type == "Exam":
            measurement_type = NodeType.EXAM_RESULT
            measurement_label = f"result {index}"
        else:
            measurement_type = NodeType.MEASUREMENT
            measurement_label = f"measurement {index}"

        measurement_node = Node(
            node_id=_node_id(case_id, measurement_label),
            type=measurement_type,
            label=measurement_label,
            attributes=(
                f"text={measurement.text};"
                f"start={measurement.start};end={measurement.end}"
            ),
        )
        nodes.append(measurement_node)

        if measurement.entity:
            entity_node_id = _node_id(case_id, measurement.entity.label)
            unit = (measurement.unit or "").lower()

            if unit in DURATION_UNITS:
                relation = Relation.HAS_DURATION
            elif unit in SIZE_UNITS:
                relation = Relation.HAS_SIZE
            elif measurement.entity.type == "Exam":
                relation = Relation.HAS_RESULT
            elif (
                measurement.entity.type in {"Medication", "Treatment"}
                and is_dose_unit(unit)
            ):
                relation = Relation.HAS_DOSE
            else:
                relation = None

            if relation:
                edges.append(
                    _edge(entity_node_id, measurement_node.node_id, relation)
                )

        if measurement.value is not None:
            value_node = Node(
                node_id=_node_id(case_id, measurement.value),
                type=NodeType.VALUE,
                label=measurement.value,
                attributes="",
            )
            nodes.append(value_node)
            edges.append(
                _edge(
                    measurement_node.node_id,
                    value_node.node_id,
                    Relation.HAS_VALUE,
                )
            )

        if measurement.unit:
            unit_node = Node(
                node_id=_node_id(case_id, measurement.unit),
                type=NodeType.UNIT,
                label=measurement.unit,
                attributes="",
            )
            nodes.append(unit_node)
            edges.append(
                _edge(
                    measurement_node.node_id,
                    unit_node.node_id,
                    Relation.HAS_UNIT,
                )
            )

        if measurement.reference_range:
            reference_label = (
                f"{measurement.reference_range.low}-"
                f"{measurement.reference_range.high}"
            )
            reference_node = Node(
                node_id=_node_id(case_id, reference_label),
                type=NodeType.REFERENCE_RANGE,
                label=reference_label,
                attributes="",
            )
            low_node = Node(
                node_id=_node_id(case_id, f"low {measurement.reference_range.low}"),
                type=NodeType.VALUE,
                label=measurement.reference_range.low,
                attributes="",
            )
            high_node = Node(
                node_id=_node_id(case_id, f"high {measurement.reference_range.high}"),
                type=NodeType.VALUE,
                label=measurement.reference_range.high,
                attributes="",
            )
            nodes.extend([reference_node, low_node, high_node])
            edges.append(
                _edge(
                    measurement_node.node_id,
                    reference_node.node_id,
                    Relation.HAS_REFERENCE_RANGE,
                )
            )
            edges.append(
                _edge(
                    reference_node.node_id,
                    low_node.node_id,
                    Relation.HAS_LOW,
                )
            )
            edges.append(
                _edge(
                    reference_node.node_id,
                    high_node.node_id,
                    Relation.HAS_HIGH,
                )
            )

        if measurement.interpretation:
            interpretation_node = Node(
                node_id=_node_id(case_id, measurement.interpretation),
                type=NodeType.INTERPRETATION,
                label=measurement.interpretation,
                attributes="",
            )
            nodes.append(interpretation_node)
            edges.append(
                _edge(
                    measurement_node.node_id,
                    interpretation_node.node_id,
                    Relation.HAS_INTERPRETATION,
                )
            )

    return nodes, edges


def load_entity_vocabulary(vocabulary_dir: str | Path = "vocabularies") -> list:
    vocabulary_dir = Path(vocabulary_dir)
    vocabulary = []

    for filename in ENTITY_FILES:
        vocabulary.extend(load_vocabulary(vocabulary_dir / filename))

    return vocabulary


def build_case_graph(
    case_id: str,
    case_text: str,
    vocabulary: list,
) -> tuple[list[Node], list]:
    patient = Entity(
        label="patient",
        type=NodeType.PATIENT.value,
        source="case",
    )
    extracted_entities = extract_entities(case_text, vocabulary)
    entities = [patient, *extracted_entities]
    measurements = extract_structured_measurements(
        case_text,
        extracted_entities,
    )

    node_map: dict[str, Node] = {}
    nodes: list[Node] = []

    for entity in entities:
        node = _entity_to_node(case_id, entity)
        if node.node_id not in node_map:
            node_map[node.node_id] = node
            nodes.append(node)

    edges = extract_case_relations(case_id, entities, case_text)

    measurement_nodes, measurement_edges = _build_measurement_graph(
        case_id,
        measurements,
    )
    for node in measurement_nodes:
        if node.node_id not in node_map:
            node_map[node.node_id] = node
            nodes.append(node)

    edges.extend(measurement_edges)
    edges = _dedupe_edges(edges)

    valid_edges = []
    for edge in edges:
        if edge.source_id in node_map and edge.target_id in node_map:
            valid_edges.append(edge)

    return nodes, valid_edges


def build_graph_from_cases(
    cases: list[dict],
    vocabulary: list,
) -> tuple[list[Node], list]:
    all_nodes: list[Node] = []
    all_edges: list = []
    seen_nodes: set[str] = set()

    for case in cases:
        case_id = case.get("case_id")
        case_text = case.get("case_text", "")
        if not case_id or not case_text:
            continue

        nodes, edges = build_case_graph(case_id, case_text, vocabulary)

        for node in nodes:
            if node.node_id not in seen_nodes:
                seen_nodes.add(node.node_id)
                all_nodes.append(node)

        all_edges.extend(edges)

    return all_nodes, all_edges


def export_graph_from_cases(
    cases: list[dict],
    vocabulary: list,
    nodes_path: str | Path,
    edges_path: str | Path,
) -> None:
    nodes, edges = build_graph_from_cases(cases, vocabulary)
    save_nodes(nodes, nodes_path)
    save_edges(edges, edges_path)


__all__ = [
    "ENTITY_FILES",
    "DURATION_UNITS",
    "SIZE_UNITS",
    "load_entity_vocabulary",
    "_build_measurement_graph",
    "build_case_graph",
    "build_graph_from_cases",
    "export_graph_from_cases",
]
