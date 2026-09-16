"""Monta o grafo canônico (nós + arestas) de cada caso clínico.

Um nó/aresta por linha, seguindo o esquema de duas tabelas do enunciado.
`Unit` é compartilhado entre casos (node_id = string da unidade) — a mesma
unidade mencionada em casos diferentes aponta pro mesmo nó. Os demais nós
são instâncias por caso (node_id prefixado por `case_id`).

Não gera nó `VocabConcept`/aresta `SAME_AS` — o código MeSH de cada match
só serve de identificador interno pro dedupe do gazetteer; não vira nó no
grafo por não agregar valor num grafo básico (decisão explícita, não é
esquecimento).

Duas passadas por sentença:
1. Symptom / Diagnosis / AnatomicalSite / Treatment-não-reclassificado /
   History — criação direta de nó + aresta com o Patient.
2. Exam (original ou Treatment reclassificado por `relations.py`) — só
   depois da passada 1, pra poder linkar `CONFIRMS/EXCLUDES/REVEALS` a um
   Diagnosis/Symptom que já ganhou node_id nesta sentença.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from kg_extraction.features.gazetteer_ner import EntityMatch, Gazetteer, find_entities_in_sentence
from kg_extraction.features.preprocessing import split_sentences
from kg_extraction.features.relations import assign_history, build_exam_result, find_finding, reclassify_treatment_matches
from kg_extraction.features.triggers import Trigger, find_triggers_in_sentence
from kg_extraction.features.value_unit_extraction import ValueUnitMatch, find_value_units

_NODE_PREFIX = {"symptom": "S", "diagnosis": "D", "exam": "E", "treatment": "T", "anatomical_site": "AS"}
_TYPE_LABEL = {
    "symptom": "Symptom",
    "diagnosis": "Diagnosis",
    "exam": "Exam",
    "treatment": "Treatment",
    "anatomical_site": "AnatomicalSite",
}
_PATIENT_RELATION = {
    "symptom": "PRESENTS_WITH",
    "diagnosis": "DIAGNOSED_WITH",
    "exam": "UNDERWENT_EXAM",
    "treatment": "UNDERWENT_TREATMENT",
    "anatomical_site": None,
}


@dataclass
class CaseGraph:
    nodes: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)


class _CaseBuilder:
    """Estado mutável de um caso: contadores de id, dedupe por (tipo, label),
    e o set global (compartilhado entre casos) de Unit."""

    def __init__(self, case_id: str, units_seen: set[str]):
        self.case_id = case_id
        self.graph = CaseGraph()
        self.counters = {entity_type: 0 for entity_type in list(_NODE_PREFIX) + ["F"]}
        self.seen: dict[tuple[str, str], str] = {}  # (tipo_efetivo, canonical) -> node_id
        self.units_seen = units_seen
        self._edge_counter = 0
        self.last_diagnosis_id: str | None = None

    def next_edge_id(self) -> str:
        self._edge_counter += 1
        return f"{self.case_id}_e{self._edge_counter}"

    def add_edge(self, source_id: str, target_id: str, relation: str, attributes: str = "") -> None:
        self.graph.edges.append(
            {
                "edge_id": self.next_edge_id(),
                "case_id": self.case_id,
                "source_id": source_id,
                "target_id": target_id,
                "relation": relation,
                "attributes": attributes,
            }
        )

    def get_or_create_unit(self, unit: str) -> str:
        node_id = f"UNIT_{unit.upper()}"
        if node_id not in self.units_seen:
            self.units_seen.add(node_id)
            self.graph.nodes.append({"node_id": node_id, "case_id": "", "type": "Unit", "label": unit, "attributes": ""})
        return node_id

    def get_or_create_entity(self, effective_type: str, canonical_label: str, match_kind: str, distance: int) -> tuple[str, bool]:
        key = (effective_type, canonical_label)
        if key in self.seen:
            return self.seen[key], False
        self.counters[effective_type] += 1
        node_id = f"{self.case_id}_{_NODE_PREFIX[effective_type]}{self.counters[effective_type]}"
        self.seen[key] = node_id
        self.graph.nodes.append(
            {
                "node_id": node_id,
                "case_id": self.case_id,
                "type": _TYPE_LABEL[effective_type],
                "label": canonical_label,
                "attributes": f"match={match_kind}; distance={distance}",
            }
        )
        return node_id, True

    def create_history(self, m: EntityMatch, patient_id: str) -> None:
        key = ("history", m.canonical_label)
        if key in self.seen:
            return
        self.counters.setdefault("history", 0)
        self.counters["history"] += 1
        node_id = f"{self.case_id}_H{self.counters['history']}"
        self.seen[key] = node_id
        self.graph.nodes.append(
            {
                "node_id": node_id,
                "case_id": self.case_id,
                "type": "History",
                "label": m.canonical_label,
                "attributes": f"category={m.entity_type}",
            }
        )
        self.add_edge(patient_id, node_id, "HAS_HISTORY")

    def create_finding(self, exam_node_id: str, relation: str, text: str) -> str:
        self.counters["F"] += 1
        node_id = f"{self.case_id}_F{self.counters['F']}"
        self.graph.nodes.append(
            {"node_id": node_id, "case_id": self.case_id, "type": "Finding", "label": text, "attributes": ""}
        )
        self.add_edge(exam_node_id, node_id, relation)
        return node_id

    def create_exam_result(self, exam_node_id: str, result: dict) -> str:
        self.counters.setdefault("R", 0)
        self.counters["R"] += 1
        node_id = f"{self.case_id}_R{self.counters['R']}"
        ref = ""
        if result.get("reference_low") and result.get("reference_high"):
            ref = f"; reference_range={result['reference_low']}-{result['reference_high']}"
        self.graph.nodes.append(
            {
                "node_id": node_id,
                "case_id": self.case_id,
                "type": "ExamResult",
                "label": f"{result['value']} {result['unit']}",
                "attributes": f"value={result['value']}{ref}",
            }
        )
        self.add_edge(exam_node_id, node_id, "HAS_RESULT")
        unit_node_id = self.get_or_create_unit(result["unit"])
        self.add_edge(node_id, unit_node_id, "HAS_UNIT")
        return node_id


def _process_sentence(sentence: str, sent_idx: int, gazetteers: dict[str, Gazetteer], triggers: list[Trigger], unit_pattern, builder: _CaseBuilder, patient_id: str) -> None:
    matches: list[EntityMatch] = find_entities_in_sentence(sentence, gazetteers, sent_idx)
    if not matches:
        return
    value_units: list[ValueUnitMatch] = find_value_units(sentence, unit_pattern)
    admin_triggers = find_triggers_in_sentence(sentence, triggers, "administration")
    result_triggers = find_triggers_in_sentence(sentence, triggers, "exam_result")
    history_triggers = find_triggers_in_sentence(sentence, triggers, "medical_history")

    reclassified = reclassify_treatment_matches(matches, value_units, admin_triggers)
    history_idx = assign_history(matches, history_triggers) - reclassified

    exam_queue: list[EntityMatch] = []
    sentence_diagnosis_ids: list[str] = []
    sentence_symptom_ids: list[str] = []
    sentence_treatment_ids: list[str] = []
    sentence_anatomical_site_ids: list[str] = []

    # Passada 1: tudo que não é exam/reclassificado-como-exam.
    for i, m in enumerate(matches):
        if i in reclassified:
            exam_queue.append(m)
            continue
        if i in history_idx:
            builder.create_history(m, patient_id)
            continue
        if m.entity_type == "exam":
            exam_queue.append(m)
            continue
        node_id, created = builder.get_or_create_entity(m.entity_type, m.canonical_label, m.match_kind, m.distance)
        if created:
            relation = _PATIENT_RELATION[m.entity_type]
            if relation:
                builder.add_edge(patient_id, node_id, relation)

        if m.entity_type == "diagnosis":
            sentence_diagnosis_ids.append(node_id)
            builder.last_diagnosis_id = node_id
        elif m.entity_type == "symptom":
            sentence_symptom_ids.append(node_id)
        elif m.entity_type == "anatomical_site":
            sentence_anatomical_site_ids.append(node_id)
        elif m.entity_type == "treatment":
            sentence_treatment_ids.append(node_id)
            if builder.last_diagnosis_id and created:
                builder.add_edge(builder.last_diagnosis_id, node_id, "TREATED_BY")

    # SUPPORTS: sintoma que co-ocorre na mesma sentença com um diagnóstico.
    for diag_id in sentence_diagnosis_ids:
        for symptom_id in sentence_symptom_ids:
            builder.add_edge(symptom_id, diag_id, "SUPPORTS")

    # AnatomicalSite: mesma regra de co-ocorrência na sentença, ligando quem
    # menciona um local do corpo junto de um diagnóstico/tratamento.
    for as_id in sentence_anatomical_site_ids:
        for diag_id in sentence_diagnosis_ids:
            builder.add_edge(diag_id, as_id, "LOCATED_IN")
        for treat_id in sentence_treatment_ids:
            builder.add_edge(treat_id, as_id, "TARGETS")

    # Passada 2: exam (original + reclassificado) -> ExamResult / Finding / CONFIRMS-EXCLUDES-REVEALS.
    for m in exam_queue:
        node_id, created = builder.get_or_create_entity("exam", m.canonical_label, m.match_kind, m.distance)
        if created:
            builder.add_edge(patient_id, node_id, "UNDERWENT_EXAM")
        for as_id in sentence_anatomical_site_ids:
            builder.add_edge(node_id, as_id, "PERFORMED_ON")

        result = build_exam_result(m, value_units)
        if result:
            result_node_id = builder.create_exam_result(node_id, result)
            for diag_id in sentence_diagnosis_ids:
                builder.add_edge(result_node_id, diag_id, "SUPPORTS")
            continue

        finding = find_finding(m, sentence, result_triggers, matches)
        if finding is None:
            continue
        if "linked_key" in finding:
            target_id = builder.seen.get(finding["linked_key"])
            if target_id:
                builder.add_edge(node_id, target_id, finding["relation"])
            continue
        finding_node_id = builder.create_finding(node_id, finding["relation"], finding["finding_text"])
        for as_id in sentence_anatomical_site_ids:
            builder.add_edge(finding_node_id, as_id, "LOCATED_IN")


def build_case_graph(
    case_row: pd.Series,
    gazetteers: dict[str, Gazetteer],
    triggers: list[Trigger],
    unit_pattern,
    units_seen: set[str],
) -> CaseGraph:
    case_id = case_row["case_id"]
    builder = _CaseBuilder(case_id, units_seen)

    patient_id = f"{case_id}_P1"
    builder.graph.nodes.append(
        {
            "node_id": patient_id,
            "case_id": case_id,
            "type": "Patient",
            "label": f"case {case_id}",
            "attributes": f"age={case_row['age']}; gender={case_row['gender']}",
        }
    )

    for sent_idx, sentence in enumerate(split_sentences(str(case_row["case_text"]))):
        _process_sentence(sentence, sent_idx, gazetteers, triggers, unit_pattern, builder, patient_id)

    return builder.graph


def build_dataset_graph(cases_df: pd.DataFrame, gazetteers: dict[str, Gazetteer], triggers: list[Trigger], unit_pattern) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_nodes, all_edges = [], []
    units_seen: set[str] = set()
    for _, case_row in cases_df.iterrows():
        graph = build_case_graph(case_row, gazetteers, triggers, unit_pattern, units_seen)
        all_nodes.extend(graph.nodes)
        all_edges.extend(graph.edges)
    return pd.DataFrame(all_nodes), pd.DataFrame(all_edges)
