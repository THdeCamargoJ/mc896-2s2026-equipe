"""Parser do descriptor file do MeSH (XML oficial da NLM) para gazetteers.

Lê `desc2025.xml` (~314MB) via `iterparse` (streaming, um `DescriptorRecord`
por vez, sem carregar a árvore inteira em memória) e gera um CSV por tipo de
entidade, filtrando os descritores pelo prefixo do seu(s) `TreeNumber`.

Cada descritor MeSH já vem com sinônimos prontos: os "Entry Terms" — todo
`Term/String` dentro de `ConceptList/Concept/TermList`. Um descritor pode
pertencer a mais de um ramo (múltiplos `TreeNumber`); nesse caso ele aparece
no CSV de todos os tipos cujo prefixo bata (a desambiguação fica pro matcher
de NER, não pra este parser).

Filtro de tamanho: cada descritor carrega em média 8-9 Entry Terms, mas a
maioria é grafia rara/histórica. Mantemos só `ConceptPreferredTermYN="Y"`
(o termo "principal" de cada conceito dentro do descritor — ainda preserva
sinônimos reais quando o descritor agrega mais de um conceito, só corta a
cauda longa de variação de grafia). Medido: reduz o total de termos do MeSH
de ~265k pra ~61k (~4.3x menor), sem colapsar pra um único nome por
descritor.
"""

from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from pathlib import Path

from kg_extraction.config import GAZETTEER_FILES, MESH_BRANCH_RULES, MESH_DESCRIPTOR_XML


def _matches_branch(tree_numbers: list[str], include: tuple[str, ...], exclude: tuple[str, ...]) -> bool:
    for tn in tree_numbers:
        if any(tn.startswith(p) for p in include) and not any(tn.startswith(p) for p in exclude):
            return True
    return False


def iter_descriptors(xml_path: Path):
    """Itera `desc2025.xml` e produz (ui, canonical, tree_numbers, synonyms) por descritor."""
    for event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag != "DescriptorRecord":
            continue
        ui = elem.findtext("DescriptorUI")
        canonical = elem.findtext("DescriptorName/String")
        tree_numbers = [tn.text for tn in elem.findall("TreeNumberList/TreeNumber") if tn.text]
        synonyms = set()
        for term in elem.findall("ConceptList/Concept/TermList/Term"):
            if term.get("ConceptPreferredTermYN") != "Y":
                continue
            term_str = term.find("String")
            if term_str is not None and term_str.text:
                synonyms.add(term_str.text.strip())
        if canonical:
            synonyms.add(canonical.strip())
        yield ui, canonical, tree_numbers, synonyms
        elem.clear()


def build_gazetteers(xml_path: Path = MESH_DESCRIPTOR_XML, output_files: dict[str, Path] = None) -> dict[str, int]:
    """Gera um CSV (`mesh_ui,canonical,synonym`) por tipo de entidade.

    Retorna a contagem de linhas (sinônimo) escritas por tipo, para log/sanity check.
    """
    output_files = output_files or GAZETTEER_FILES
    writers = {}
    handles = []
    counts = {entity_type: 0 for entity_type in output_files}
    try:
        for entity_type, path in output_files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            fh = open(path, "w", newline="", encoding="utf-8")
            handles.append(fh)
            writer = csv.writer(fh)
            writer.writerow(["mesh_ui", "canonical", "synonym"])
            writers[entity_type] = writer

        for ui, canonical, tree_numbers, synonyms in iter_descriptors(xml_path):
            if not canonical:
                continue
            for entity_type, rule in MESH_BRANCH_RULES.items():
                if _matches_branch(tree_numbers, rule["include"], rule["exclude"]):
                    writer = writers[entity_type]
                    for syn in synonyms:
                        writer.writerow([ui, canonical, syn.lower()])
                        counts[entity_type] += 1
    finally:
        for fh in handles:
            fh.close()
    return counts


if __name__ == "__main__":
    counts = build_gazetteers()
    for entity_type, n in counts.items():
        print(f"{entity_type}: {n} sinônimos -> {GAZETTEER_FILES[entity_type]}")
