from src.extraction.entities import Entity
from src.extraction.relations import extract_case_relations
from src.graph.schema import Relation


def _entity(text, label, entity_type, surface=None):
    surface = surface or label
    start = text.lower().index(surface.lower())
    return Entity(
        label=label,
        type=entity_type,
        positions=[(start, start + len(surface))],
    )


def test_extracts_context_relations():
    text = (
        "Patient had a history of hypertension. "
        "Patient presented with abdominal pain and underwent a CT scan, "
        "which confirmed a solid mass in the pancreas. "
        "The diagnosis of acute pancreatitis was treated with intravenous fluids. "
        "Patient recovered."
    )
    entities = [
        Entity(label="patient", type="Patient"),
        _entity(text, "hypertension", "Diagnosis"),
        _entity(text, "abdominal pain", "Symptom"),
        _entity(text, "computed tomography", "Exam", "CT scan"),
        _entity(text, "solid mass", "Finding"),
        _entity(text, "pancreas", "AnatomicalSite"),
        _entity(text, "pancreatitis", "Diagnosis"),
        _entity(text, "intravenous fluids", "Treatment"),
        _entity(text, "confirmed", "Status"),
        _entity(text, "acute", "Course"),
        _entity(text, "recovery", "Outcome", "recovered"),
    ]

    edges = extract_case_relations("case_001", entities, text)
    relations = {
        (edge.source_id, edge.target_id, edge.relation)
        for edge in edges
    }

    assert (
        "case_001:patient",
        "case_001:hypertension",
        Relation.HAS_HISTORY,
    ) in relations
    assert (
        "case_001:patient",
        "case_001:pancreatitis",
        Relation.DIAGNOSED_WITH,
    ) in relations
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
        "case_001:computed tomography",
        "case_001:solid mass",
        Relation.CONFIRMS,
    ) in relations
    assert (
        "case_001:pancreatitis",
        "case_001:intravenous fluids",
        Relation.TREATED_BY,
    ) in relations
    assert (
        "case_001:pancreatitis",
        "case_001:pancreas",
        Relation.LOCATED_IN,
    ) in relations
    assert (
        "case_001:pancreatitis",
        "case_001:confirmed",
        Relation.HAS_STATUS,
    ) in relations
    assert (
        "case_001:pancreatitis",
        "case_001:acute",
        Relation.HAS_COURSE,
    ) in relations
    assert (
        "case_001:patient",
        "case_001:recovery",
        Relation.HAS_OUTCOME,
    ) in relations


def test_negation_avoids_positive_relations_and_creates_excludes():
    text = (
        "The patient denied abdominal pain. "
        "CT scan was negative for a solid mass. "
        "The patient had no hypertension."
    )
    entities = [
        Entity(label="patient", type="Patient"),
        _entity(text, "abdominal pain", "Symptom"),
        _entity(text, "computed tomography", "Exam", "CT scan"),
        _entity(text, "solid mass", "Finding"),
        _entity(text, "hypertension", "Diagnosis"),
    ]

    edges = extract_case_relations("case_002", entities, text)
    relations = {
        (edge.source_id, edge.target_id, edge.relation)
        for edge in edges
    }

    assert (
        "case_002:computed tomography",
        "case_002:solid mass",
        Relation.EXCLUDES,
    ) in relations
    assert (
        "case_002:patient",
        "case_002:abdominal pain",
        Relation.PRESENTS_WITH,
    ) not in relations
    assert (
        "case_002:patient",
        "case_002:hypertension",
        Relation.DIAGNOSED_WITH,
    ) not in relations
