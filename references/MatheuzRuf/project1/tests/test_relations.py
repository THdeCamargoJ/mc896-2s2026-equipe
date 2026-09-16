from src.extraction.entities import Entity
from src.extraction.relations import extract_case_relations
from src.graph.schema import Relation


def test_extract_case_relations_builds_patient_links():
    entities = [
        Entity(label="patient", type="Patient", positions=[(0, 7)]),
        Entity(label="abdominal pain", type="Symptom", positions=[(8, 23)]),
        Entity(label="ct scan", type="Exam", positions=[(24, 31)]),
        Entity(label="pancreatitis", type="Diagnosis", positions=[(32, 44)]),
        Entity(label="ibuprofen", type="Medication", positions=[(45, 54)]),
    ]

    relations = extract_case_relations("case_001", entities)

    relations_by_name = {(r.source_id, r.target_id, r.relation) for r in relations}

    assert ("case_001:patient", "case_001:abdominal pain", Relation.PRESENTS_WITH) in relations_by_name
    assert ("case_001:patient", "case_001:ct scan", Relation.UNDERWENT_EXAM) in relations_by_name
    assert ("case_001:pancreatitis", "case_001:abdominal pain", Relation.HAS_FINDING) in relations_by_name
    assert ("case_001:patient", "case_001:ibuprofen", Relation.TREATED_BY) in relations_by_name
