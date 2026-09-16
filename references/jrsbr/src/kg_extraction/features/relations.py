"""Regras de relação: co-ocorrência + palavras-gatilho, tudo baseado em
proximidade de caracteres dentro da mesma sentença. Três decisões aqui:

1. `reclassify_treatment_matches` — uma substância do ramo D do MeSH
   ("Chemicals and Drugs") aparece tanto em "treated with **prednisone**"
   (tratamento de verdade) quanto em "**hemoglobin** was 9 g/dL" (resultado
   de exame, não tratamento). Sem gatilho de administração por perto E com
   valor+unidade logo depois, a entidade é reclassificada de Treatment pra
   Exam.
2. `assign_history` — "history of X" (e variações) reclassifica X de
   ocorrência atual pra `MedicalHistory`.
3. `build_exam_result` / `find_finding` — pra cada Exam (original ou
   reclassificado), tenta achar valor+unidade adjacente (`ExamResult`);
   sem valor, tenta gatilho textual (confirmed/excluded/showed...) e liga
   direto num Diagnosis/Symptom já encontrado na sentença, ou cria um
   `Finding` com o texto bruto se não bater com nenhum vocabulário.
"""

from __future__ import annotations

from kg_extraction.features.gazetteer_ner import EntityMatch
from kg_extraction.features.triggers import TriggerMatch
from kg_extraction.features.value_unit_extraction import ValueUnitMatch

ADMIN_WINDOW = 40
RESULT_VALUE_WINDOW = 20
RESULT_TRIGGER_WINDOW = 60
HISTORY_WINDOW = 80

_POLARITY_TO_RELATION = {"positive": "CONFIRMS", "negative": "EXCLUDES", "neutral": "REVEALS"}


def _before(pos: int, triggers: list[TriggerMatch], window: int) -> list[TriggerMatch]:
    return [t for t in triggers if t.end <= pos and pos - t.end <= window]


def reclassify_treatment_matches(
    matches: list[EntityMatch], value_units: list[ValueUnitMatch], admin_triggers: list[TriggerMatch]
) -> set[int]:
    reclassified = set()
    for i, m in enumerate(matches):
        if m.entity_type != "treatment":
            continue
        if _before(m.start, admin_triggers, ADMIN_WINDOW):
            continue
        if any(0 <= vu.start - m.end <= RESULT_VALUE_WINDOW for vu in value_units):
            reclassified.add(i)
    return reclassified


def assign_history(matches: list[EntityMatch], history_triggers: list[TriggerMatch]) -> set[int]:
    history_idx = set()
    for i, m in enumerate(matches):
        if m.entity_type not in ("diagnosis", "symptom", "treatment"):
            continue
        if _before(m.start, history_triggers, HISTORY_WINDOW):
            history_idx.add(i)
    return history_idx


def build_exam_result(m: EntityMatch, value_units: list[ValueUnitMatch]) -> dict | None:
    adjacent = [vu for vu in value_units if 0 <= vu.start - m.end <= RESULT_VALUE_WINDOW]
    if not adjacent:
        return None
    vu = min(adjacent, key=lambda x: x.start)
    return {
        "value": vu.value,
        "unit": vu.unit,
        "reference_low": vu.reference_low,
        "reference_high": vu.reference_high,
    }


def find_finding(
    m: EntityMatch, sentence: str, result_triggers: list[TriggerMatch], other_matches: list[EntityMatch]
) -> dict | None:
    nearby = [
        t
        for t in result_triggers
        if min(abs(t.start - m.end), abs(m.start - t.end)) <= RESULT_TRIGGER_WINDOW
    ]
    if not nearby:
        return None
    trigger = min(nearby, key=lambda t: min(abs(t.start - m.end), abs(m.start - t.end)))
    relation = _POLARITY_TO_RELATION[trigger.trigger.polarity]

    if trigger.start >= m.end:
        span_start, span_end = trigger.end, min(len(sentence), trigger.end + 60)
    else:
        span_start, span_end = max(0, trigger.start - 60), trigger.start

    for other in other_matches:
        if other is m or other.entity_type not in ("diagnosis", "symptom"):
            continue
        if not (other.end <= span_start or other.start >= span_end):
            return {"relation": relation, "linked_key": (other.entity_type, other.canonical_label)}

    raw_text = sentence[span_start:span_end].strip(" ,.;:")
    if not raw_text:
        return None
    return {"relation": relation, "finding_text": raw_text}
