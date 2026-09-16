"""Extração de valor+unidade (+ faixa de referência) por regex.

O padrão de unidade é construído dinamicamente a partir de `units.txt` (lista
controlada, sem fuzzy — ver README). Também reconhece `reference range X-Y`
adjacente ao valor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kg_extraction.config import UNITS_FILE


def load_units(path: Path = UNITS_FILE) -> list[str]:
    units = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            units.append(line)
    return sorted(units, key=len, reverse=True)


@dataclass
class ValueUnitMatch:
    value: str
    unit: str
    reference_low: str | None
    reference_high: str | None
    start: int
    end: int


def build_value_unit_pattern(units: list[str]) -> re.Pattern:
    unit_alt = "|".join(re.escape(u) for u in units)
    return re.compile(
        rf"(?P<value>\d[\d,\.]*)\s*(?P<unit>{unit_alt})\b"
        rf"(?:\s*,?\s*reference range\s*(?P<ref_low>\d[\d,\.]*)\s*-\s*(?P<ref_high>\d[\d,\.]*))?",
        re.IGNORECASE,
    )


def find_value_units(sentence: str, pattern: re.Pattern) -> list[ValueUnitMatch]:
    matches = []
    for m in pattern.finditer(sentence):
        matches.append(
            ValueUnitMatch(
                value=m.group("value"),
                unit=m.group("unit"),
                reference_low=m.group("ref_low"),
                reference_high=m.group("ref_high"),
                start=m.start(),
                end=m.end(),
            )
        )
    return matches
