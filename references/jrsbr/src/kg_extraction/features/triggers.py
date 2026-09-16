"""Palavras-gatilho (`references/vocabularies/triggers.csv`): expressões que
sinalizam um papel especial pra entidade vizinha na sentença — resultado de
exame positivo/negativo/neutro, histórico clínico prévio, ou administração
de tratamento (usada pra distinguir substância *administrada* de substância
só *medida em exame*, ver `reclassify_treatment_as_exam`).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from kg_extraction.config import TRIGGERS_FILE


@dataclass
class Trigger:
    phrase: str
    polarity: str
    use: str


@dataclass
class TriggerMatch:
    trigger: Trigger
    start: int
    end: int


def load_triggers(path: Path = TRIGGERS_FILE) -> list[Trigger]:
    triggers = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            triggers.append(Trigger(row["trigger"], row["polarity"], row["use"]))
    return sorted(triggers, key=lambda t: -len(t.phrase.split()))


def find_triggers_in_sentence(sentence: str, triggers: list[Trigger], use: str) -> list[TriggerMatch]:
    matches = []
    for trigger in triggers:
        if trigger.use != use:
            continue
        pattern = re.compile(r"\b" + re.escape(trigger.phrase) + r"\b", re.IGNORECASE)
        for m in pattern.finditer(sentence):
            matches.append(TriggerMatch(trigger, m.start(), m.end()))
    matches.sort(key=lambda tm: tm.start)
    return matches
