import re
from dataclasses import dataclass, field

from src.vocab import VocabularyEntry


@dataclass
class Entity:
    """
    Uma entidade clínica identificada no texto via dictionary matching.

    label:
        Forma canônica da entidade (VocabularyEntry.term).

    type:
        Tipo da entidade, vindo diretamente do vocabulário (ex.: "Symptom",
        "Diagnosis", "Exam", "Treatment", "Medication", "AnatomicalSite").

    positions:
        Lista de (start, end) com todas as posições, em caracteres no
        texto original, em que a entidade foi encontrada.

    surface_forms:
        Formas de superfície efetivamente encontradas no texto (podem
        divergir do label canônico quando um alias é utilizado).

    source:
        Origem do conceito no vocabulário, por exemplo: manual, MeSH, LOINC.

    code:
        Código externo, quando disponível.
    """

    label: str
    type: str
    positions: list[tuple[int, int]] = field(default_factory=list)
    surface_forms: list[str] = field(default_factory=list)
    source: str = "manual"
    code: str = ""

    @property
    def count(self) -> int:
        """
        Quantidade de vezes que a entidade aparece no texto.
        """
        return len(self.positions)


def _build_pattern(
    vocabulary: list[VocabularyEntry],
) -> tuple[re.Pattern, dict[str, VocabularyEntry]]:
    """
    Constrói um único regex de alternação a partir de todos os termos e
    aliases do vocabulário, e um mapeamento forma de superfície -> entrada.

    As alternativas são ordenadas da mais longa para a mais curta, para
    que termos mais específicos tenham prioridade sobre termos mais curtos
    que sejam prefixo de outros.
    """

    surface_to_entry: dict[str, VocabularyEntry] = {}

    for entry in vocabulary:
        for surface in entry.all_terms:
            key = surface.strip().lower()

            if not key:
                continue

            # Mantém a primeira ocorrência em caso de forma de superfície
            # repetida entre entradas de vocabulários diferentes.
            surface_to_entry.setdefault(key, entry)

    surfaces = sorted(surface_to_entry.keys(), key=len, reverse=True)

    alternation = "|".join(re.escape(surface) for surface in surfaces)
    pattern = re.compile(rf"\b(?:{alternation})\b", re.IGNORECASE)

    return pattern, surface_to_entry


def extract_entities(text: str, vocabulary: list[VocabularyEntry]) -> list[Entity]:
    """
    Extrai entidades clínicas de um texto via dictionary matching contra
    um vocabulário.

    A categoria de cada entidade vem exclusivamente do vocabulário, nenhuma
    heurística estatística (TF-IDF, vector space model, etc.) é utilizada.

    Cada entidade é normalizada para seu label canônico. Todas as
    ocorrências de um mesmo conceito no texto são agregadas em uma única
    entrada, evitando duplicatas, mas as posições de cada ocorrência são
    preservadas para uso futuro em relation extraction.

    O casamento é feito sobre o texto original (não normalizado), para que
    as posições retornadas correspondam ao case_text original.
    """

    if not vocabulary or not text:
        return []

    pattern, surface_to_entry = _build_pattern(vocabulary)

    entities_by_key: dict[tuple[str, str], Entity] = {}
    order = []

    for match in pattern.finditer(text):
        surface = match.group(0)
        entry = surface_to_entry[surface.lower()]

        key = (entry.term, entry.type)

        if key not in entities_by_key:
            entities_by_key[key] = Entity(
                label=entry.term,
                type=entry.type,
                source=entry.source,
                code=entry.code,
            )
            order.append(key)

        entity = entities_by_key[key]
        entity.positions.append((match.start(), match.end()))

        if surface not in entity.surface_forms:
            entity.surface_forms.append(surface)

    return [entities_by_key[key] for key in order]