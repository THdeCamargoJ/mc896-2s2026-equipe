import re

from src.graph.schema import Edge, Relation
from src.extraction.entities import Entity


NEGATION_PATTERN = re.compile(
    r"(?:\bno\b|\bwithout\b|\bdenied\b|\babsence of\b|\bnegative for\b)"
    r"(?:\s+\w+){0,5}\s*$",
    re.IGNORECASE,
)

HISTORY_PATTERNS = [
    "history of",
    "history includes",
    "past medical history of",
]

CONFIRM_PATTERNS = [
    "confirmed",
    "confirming",
]


def _node_id(case_id: str, label: str) -> str:
    """Cria um identificador estavel do no mantendo a label legivel."""
    normalized = " ".join(label.strip().lower().split())
    return f"{case_id}:{normalized}"


def _dedupe_edges(edges: list[Edge]) -> list[Edge]:
    """Remove arestas duplicadas preservando ordem."""
    seen: set[tuple[str, str, str]] = set()
    unique: list[Edge] = []

    for edge in edges:
        key = (edge.source_id, edge.target_id, edge.relation.value)
        if key in seen:
            continue
        seen.add(key)
        unique.append(edge)

    return unique


def _is_negated_position(case_text: str, position: int) -> bool:
    context = case_text[max(0, position - 80):position]
    return NEGATION_PATTERN.search(context) is not None


def _has_positive_mention(case_text: str, entity: Entity) -> bool:
    if not case_text or not entity.positions:
        return True

    return any(
        not _is_negated_position(case_text, start)
        for start, _ in entity.positions
    )


def _has_negated_mention(case_text: str, entity: Entity) -> bool:
    if not case_text:
        return False

    return any(
        _is_negated_position(case_text, start)
        for start, _ in entity.positions
    )


def _has_context_before(
    case_text: str,
    entity: Entity,
    patterns: list[str],
) -> bool:
    if not case_text:
        return False

    for start, _ in entity.positions:
        context = case_text[max(0, start - 80):start].lower()
        if any(pattern in context for pattern in patterns):
            return True

    return False


def extract_case_relations(
    case_id: str,
    entities: list[Entity],
    case_text: str = "",
) -> list[Edge]:
    """
    Gera arestas de relacionamento para um unico caso clinico.

    A logica e intencionalmente simples e baseada em regras:
    - Patient -> Symptom : PRESENTS_WITH
    - Patient -> Exam : UNDERWENT_EXAM
    - Patient -> Diagnosis : HAS_HISTORY ou DIAGNOSED_WITH
    - Exam -> Finding : REVEALS, CONFIRMS ou EXCLUDES
    - Diagnosis -> Symptom : HAS_FINDING
    - Diagnosis -> Treatment : TREATED_BY
    - Patient -> Medication : TREATED_BY
    - Patient -> Outcome : HAS_OUTCOME

    Os nos do grafo sao identificados por "case_id:label_normalizada".
    """

    entities_by_type: dict[str, list[Entity]] = {}
    for entity in entities:
        entities_by_type.setdefault(entity.type, []).append(entity)

    edges = []

    patient_entities = entities_by_type.get("Patient", [])
    symptom_entities = entities_by_type.get("Symptom", [])
    exam_entities = entities_by_type.get("Exam", [])
    finding_entities = entities_by_type.get("Finding", [])
    diagnosis_entities = entities_by_type.get("Diagnosis", [])
    treatment_entities = entities_by_type.get("Treatment", [])
    medication_entities = entities_by_type.get("Medication", [])
    outcome_entities = entities_by_type.get("Outcome", [])
    anatomical_site_entities = entities_by_type.get("AnatomicalSite", [])
    status_entities = entities_by_type.get("Status", [])
    course_entities = entities_by_type.get("Course", [])

    for patient in patient_entities:
        patient_node = _node_id(case_id, patient.label)
        for symptom in symptom_entities:
            if not _has_positive_mention(case_text, symptom):
                continue

            symptom_node = _node_id(case_id, symptom.label)
            edges.append(
                Edge(
                    edge_id=f"{patient_node}->{symptom_node}:{Relation.PRESENTS_WITH.value}",
                    source_id=patient_node,
                    target_id=symptom_node,
                    relation=Relation.PRESENTS_WITH,
                    attributes="",
                )
            )

        for exam in exam_entities:
            if not _has_positive_mention(case_text, exam):
                continue

            exam_node = _node_id(case_id, exam.label)
            edges.append(
                Edge(
                    edge_id=f"{patient_node}->{exam_node}:{Relation.UNDERWENT_EXAM.value}",
                    source_id=patient_node,
                    target_id=exam_node,
                    relation=Relation.UNDERWENT_EXAM,
                    attributes="",
                )
            )

        for medication in medication_entities:
            if not _has_positive_mention(case_text, medication):
                continue

            medication_node = _node_id(case_id, medication.label)
            edges.append(
                Edge(
                    edge_id=f"{patient_node}->{medication_node}:{Relation.TREATED_BY.value}",
                    source_id=patient_node,
                    target_id=medication_node,
                    relation=Relation.TREATED_BY,
                    attributes="",
                )
            )

        for diagnosis in diagnosis_entities:
            if not _has_positive_mention(case_text, diagnosis):
                continue

            diagnosis_node = _node_id(case_id, diagnosis.label)
            if _has_context_before(case_text, diagnosis, HISTORY_PATTERNS):
                relation = Relation.HAS_HISTORY
            else:
                relation = Relation.DIAGNOSED_WITH

            edges.append(
                Edge(
                    edge_id=f"{patient_node}->{diagnosis_node}:{relation.value}",
                    source_id=patient_node,
                    target_id=diagnosis_node,
                    relation=relation,
                    attributes="",
                )
            )

        for outcome in outcome_entities:
            if not _has_positive_mention(case_text, outcome):
                continue

            outcome_node = _node_id(case_id, outcome.label)
            edges.append(
                Edge(
                    edge_id=f"{patient_node}->{outcome_node}:{Relation.HAS_OUTCOME.value}",
                    source_id=patient_node,
                    target_id=outcome_node,
                    relation=Relation.HAS_OUTCOME,
                    attributes="",
                )
            )

    for diagnosis in diagnosis_entities:
        if not _has_positive_mention(case_text, diagnosis):
            continue

        diagnosis_node = _node_id(case_id, diagnosis.label)
        for symptom in symptom_entities:
            if not _has_positive_mention(case_text, symptom):
                continue

            symptom_node = _node_id(case_id, symptom.label)
            edges.append(
                Edge(
                    edge_id=f"{diagnosis_node}->{symptom_node}:{Relation.HAS_FINDING.value}",
                    source_id=diagnosis_node,
                    target_id=symptom_node,
                    relation=Relation.HAS_FINDING,
                    attributes="",
                )
            )

        for treatment in [*treatment_entities, *medication_entities]:
            if not _has_positive_mention(case_text, treatment):
                continue

            treatment_node = _node_id(case_id, treatment.label)
            edges.append(
                Edge(
                    edge_id=f"{diagnosis_node}->{treatment_node}:{Relation.TREATED_BY.value}",
                    source_id=diagnosis_node,
                    target_id=treatment_node,
                    relation=Relation.TREATED_BY,
                    attributes="",
                )
            )

        for anatomical_site in anatomical_site_entities:
            anatomical_site_node = _node_id(case_id, anatomical_site.label)
            edges.append(
                Edge(
                    edge_id=f"{diagnosis_node}->{anatomical_site_node}:{Relation.LOCATED_IN.value}",
                    source_id=diagnosis_node,
                    target_id=anatomical_site_node,
                    relation=Relation.LOCATED_IN,
                    attributes="",
                )
            )

        for status in status_entities:
            status_node = _node_id(case_id, status.label)
            edges.append(
                Edge(
                    edge_id=f"{diagnosis_node}->{status_node}:{Relation.HAS_STATUS.value}",
                    source_id=diagnosis_node,
                    target_id=status_node,
                    relation=Relation.HAS_STATUS,
                    attributes="",
                )
            )

        for course in course_entities:
            course_node = _node_id(case_id, course.label)
            edges.append(
                Edge(
                    edge_id=f"{diagnosis_node}->{course_node}:{Relation.HAS_COURSE.value}",
                    source_id=diagnosis_node,
                    target_id=course_node,
                    relation=Relation.HAS_COURSE,
                    attributes="",
                )
            )

    for exam in exam_entities:
        exam_node = _node_id(case_id, exam.label)
        for finding in finding_entities:
            finding_node = _node_id(case_id, finding.label)

            if _has_negated_mention(case_text, finding):
                relation = Relation.EXCLUDES
            elif _has_context_before(case_text, finding, CONFIRM_PATTERNS):
                relation = Relation.CONFIRMS
            else:
                relation = Relation.REVEALS

            edges.append(
                Edge(
                    edge_id=f"{exam_node}->{finding_node}:{relation.value}",
                    source_id=exam_node,
                    target_id=finding_node,
                    relation=relation,
                    attributes="",
                )
            )

    for finding in finding_entities:
        if not _has_positive_mention(case_text, finding):
            continue

        finding_node = _node_id(case_id, finding.label)
        for anatomical_site in anatomical_site_entities:
            anatomical_site_node = _node_id(case_id, anatomical_site.label)
            edges.append(
                Edge(
                    edge_id=f"{finding_node}->{anatomical_site_node}:{Relation.LOCATED_IN.value}",
                    source_id=finding_node,
                    target_id=anatomical_site_node,
                    relation=Relation.LOCATED_IN,
                    attributes="",
                )
            )

        for status in status_entities:
            status_node = _node_id(case_id, status.label)
            edges.append(
                Edge(
                    edge_id=f"{finding_node}->{status_node}:{Relation.HAS_STATUS.value}",
                    source_id=finding_node,
                    target_id=status_node,
                    relation=Relation.HAS_STATUS,
                    attributes="",
                )
            )

        for course in course_entities:
            course_node = _node_id(case_id, course.label)
            edges.append(
                Edge(
                    edge_id=f"{finding_node}->{course_node}:{Relation.HAS_COURSE.value}",
                    source_id=finding_node,
                    target_id=course_node,
                    relation=Relation.HAS_COURSE,
                    attributes="",
                )
            )

    return _dedupe_edges(edges)


__all__ = [
    "_node_id",
    "_dedupe_edges",
    "_has_positive_mention",
    "_has_negated_mention",
    "_has_context_before",
    "extract_case_relations",
]
