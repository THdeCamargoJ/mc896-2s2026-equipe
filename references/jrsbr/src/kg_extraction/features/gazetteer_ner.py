"""NER por gazetteer: exato primeiro, fuzzy (Damerau-Levenshtein) como fallback.

Fase 1 (exato): regex `\\b<sinônimo>\\b` na sentença inteira, mais longo
primeiro — resolve multi-palavra ("heart attack") sem tokenizar, igual
abordagem clássica de gazetteer.

Fase 2 (fuzzy): só roda sobre o que sobrou não-ocupado da fase 1. Gera
janelas deslizantes de N palavras (N = tamanhos de sinônimo realmente
presentes naquele gazetteer, até `MAX_FUZZY_WINDOW_WORDS`), busca a
BK-tree do tipo de entidade e aceita se `distância <= floor(FUZZY_RATIO *
len(sinônimo))`. Cobre erro de digitação/pequena variação ("heart-attack"
vs "heart attack") sem exigir forma de superfície exata no dicionário.

Em ambas as fases, uma máscara `occupied[]` evita sobreposição de spans.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from math import ceil
from pathlib import Path

from kg_extraction.config import (
    ENTITY_TYPE_PRIORITY,
    EXCLUDED_MESH_UI,
    FUZZY_ENTITY_TYPES,
    FUZZY_MAX_ABS_DISTANCE,
    FUZZY_MIN_LEN,
    FUZZY_RATIO,
    MAX_FUZZY_WINDOW_WORDS,
)
from kg_extraction.features.aho_corasick import AhoCorasick
from kg_extraction.features.damerau_levenshtein import BKTree, max_allowed_distance
from kg_extraction.features.preprocessing import normalize, tokenize_with_spans

_WORD_CHAR = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


@dataclass
class GazetteerEntry:
    entity_type: str
    mesh_ui: str
    canonical: str
    synonym: str  # já normalizado (lowercase)


@dataclass
class EntityMatch:
    entity_type: str
    mesh_ui: str
    canonical_label: str
    matched_text: str
    start: int
    end: int
    sentence_index: int
    match_kind: str  # "exact" | "fuzzy"
    distance: int


class Gazetteer:
    def __init__(self, entity_type: str, entries: list[GazetteerEntry]):
        self.entity_type = entity_type
        self.synonym_to_entries: dict[str, list[GazetteerEntry]] = {}
        for e in entries:
            self.synonym_to_entries.setdefault(e.synonym, []).append(e)

        unique_synonyms = list(self.synonym_to_entries.keys())

        self.automaton = AhoCorasick()
        for syn in unique_synonyms:
            self.automaton.add(syn)
        self.automaton.build()

        self.bk_tree = BKTree()
        self.word_counts: list[int] = []
        if entity_type in FUZZY_ENTITY_TYPES:
            for syn in unique_synonyms:
                self.bk_tree.add(syn)
            self.word_counts = sorted(
                {n for s in unique_synonyms if (n := len(s.split())) <= MAX_FUZZY_WINDOW_WORDS},
                reverse=True,
            )

    def entry_for(self, synonym: str) -> GazetteerEntry:
        return self.synonym_to_entries[synonym][0]


def load_gazetteer_csv(path: Path, entity_type: str) -> list[GazetteerEntry]:
    entries = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["mesh_ui"] in EXCLUDED_MESH_UI:
                continue
            entries.append(
                GazetteerEntry(
                    entity_type=entity_type,
                    mesh_ui=row["mesh_ui"],
                    canonical=row["canonical"],
                    synonym=row["synonym"],
                )
            )
    return entries


def load_all_gazetteers(paths: dict[str, Path]) -> dict[str, Gazetteer]:
    return {
        entity_type: Gazetteer(entity_type, load_gazetteer_csv(path, entity_type))
        for entity_type, path in paths.items()
    }


def _is_word_boundary(text: str, start: int, end: int) -> bool:
    before_ok = start == 0 or text[start - 1] not in _WORD_CHAR
    after_ok = end == len(text) or text[end] not in _WORD_CHAR
    return before_ok and after_ok


def _find_exact_matches(sentence: str, gazetteers: dict[str, Gazetteer]) -> list[tuple[int, int, str, str]]:
    # .lower() preserva comprimento/posições pra texto em inglês (ASCII) —
    # não vale em geral pra todo Unicode, mas é seguro pro corpus MultiCaRe.
    lowered = sentence.lower()
    found = []
    for entity_type, gz in gazetteers.items():
        for start, end, synonym in gz.automaton.search(lowered):
            if _is_word_boundary(lowered, start, end):
                found.append((start, end, entity_type, synonym))
    found.sort(key=lambda x: -(x[1] - x[0]))
    return found


def _find_fuzzy_candidates(
    sentence: str, gazetteers: dict[str, Gazetteer], occupied: list[bool]
) -> list[tuple[int, int, str, str, int]]:
    tokens = tokenize_with_spans(sentence)
    n_tokens = len(tokens)
    candidates = []
    for entity_type, gz in gazetteers.items():
        if entity_type not in FUZZY_ENTITY_TYPES:
            continue
        for w in gz.word_counts:
            if w > n_tokens:
                continue
            for i in range(0, n_tokens - w + 1):
                start, end = tokens[i][1], tokens[i + w - 1][2]
                if any(occupied[start:end]):
                    continue
                candidate_text = normalize(sentence[start:end])
                query_radius = min(ceil(FUZZY_RATIO * len(candidate_text)), FUZZY_MAX_ABS_DISTANCE)
                for syn, dist in gz.bk_tree.query(candidate_text, query_radius):
                    allowed = max_allowed_distance(len(syn), FUZZY_RATIO, FUZZY_MIN_LEN)
                    if dist <= allowed:
                        candidates.append((start, end, entity_type, syn, dist))
    priority_index = {t: i for i, t in enumerate(ENTITY_TYPE_PRIORITY)}
    candidates.sort(key=lambda c: (c[4], -(c[1] - c[0]), priority_index.get(c[2], len(priority_index))))
    return candidates


def find_entities_in_sentence(
    sentence: str, gazetteers: dict[str, Gazetteer], sentence_index: int
) -> list[EntityMatch]:
    occupied = [False] * len(sentence)
    matches: list[EntityMatch] = []

    for start, end, entity_type, synonym in _find_exact_matches(sentence, gazetteers):
        if any(occupied[start:end]):
            continue
        for i in range(start, end):
            occupied[i] = True
        entry = gazetteers[entity_type].entry_for(synonym)
        matches.append(
            EntityMatch(
                entity_type, entry.mesh_ui, entry.canonical, sentence[start:end],
                start, end, sentence_index, "exact", 0,
            )
        )

    for start, end, entity_type, synonym, dist in _find_fuzzy_candidates(sentence, gazetteers, occupied):
        if any(occupied[start:end]):
            continue
        for i in range(start, end):
            occupied[i] = True
        entry = gazetteers[entity_type].entry_for(synonym)
        matches.append(
            EntityMatch(
                entity_type, entry.mesh_ui, entry.canonical, sentence[start:end],
                start, end, sentence_index, "fuzzy", dist,
            )
        )

    matches.sort(key=lambda m: m.start)
    return matches
