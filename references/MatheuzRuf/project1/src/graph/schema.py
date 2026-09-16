from dataclasses import dataclass
from enum import Enum
from typing import Optional


class NodeType(str, Enum):
    """Tipos de nós utilizados no Knowledge Graph."""

    PATIENT = "Patient"
    HISTORY = "History"
    SYMPTOM = "Symptom"
    FINDING = "Finding"
    EXAM = "Exam"
    EXAM_RESULT = "ExamResult"
    DIAGNOSIS = "Diagnosis"
    MEDICATION = "Medication"
    TREATMENT = "Treatment"
    OUTCOME = "Outcome"

    # Nós utilizados para decomposição de atributos
    MEASUREMENT = "Measurement"
    VALUE = "Value"
    UNIT = "Unit"
    REFERENCE_RANGE = "ReferenceRange"
    INTERPRETATION = "Interpretation"
    ANATOMICAL_SITE = "AnatomicalSite"
    STATUS = "Status"
    COURSE = "Course"

    # Ligação com vocabulários controlados
    VOCAB_CONCEPT = "VocabConcept"


class Relation(str, Enum):
    """Relações utilizadas no Knowledge Graph."""

    # Relações clínicas
    HAS_HISTORY = "HAS_HISTORY"
    PRESENTS_WITH = "PRESENTS_WITH"
    HAS_FINDING = "HAS_FINDING"
    UNDERWENT_EXAM = "UNDERWENT_EXAM"
    HAS_RESULT = "HAS_RESULT"
    REVEALS = "REVEALS"
    CONFIRMS = "CONFIRMS"
    EXCLUDES = "EXCLUDES"
    SUPPORTS = "SUPPORTS"
    PREDISPOSES_TO = "PREDISPOSES_TO"
    DIAGNOSED_WITH = "DIAGNOSED_WITH"
    TREATED_BY = "TREATED_BY"
    TARGETS = "TARGETS"
    HAS_OUTCOME = "HAS_OUTCOME"
    LEADS_TO = "LEADS_TO"

    # Relações de atributos
    HAS_DURATION = "HAS_DURATION"
    HAS_SIZE = "HAS_SIZE"
    HAS_DOSE = "HAS_DOSE"
    LOCATED_IN = "LOCATED_IN"
    HAS_VALUE = "HAS_VALUE"
    HAS_UNIT = "HAS_UNIT"
    HAS_REFERENCE_RANGE = "HAS_REFERENCE_RANGE"
    HAS_LOW = "HAS_LOW"
    HAS_HIGH = "HAS_HIGH"
    HAS_INTERPRETATION = "HAS_INTERPRETATION"
    HAS_STATUS = "HAS_STATUS"
    HAS_COURSE = "HAS_COURSE"

    # Vocabulários controlados
    SAME_AS = "SAME_AS"


@dataclass
class Node:
    """Representa um nó do Knowledge Graph."""

    node_id: str
    type: NodeType
    label: str
    attributes: str = ""

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "type": self.type.value,
            "label": self.label,
            "attributes": self.attributes,
        }


@dataclass
class Edge:
    """Representa uma aresta do Knowledge Graph."""

    edge_id: str
    source_id: str
    target_id: str
    relation: Relation
    attributes: str = ""

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation.value,
            "attributes": self.attributes,
        }
