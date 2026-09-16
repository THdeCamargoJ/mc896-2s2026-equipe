"""Caminhos e constantes compartilhadas do pipeline de extração."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA_RAW = ROOT / "data" / "raw" / "multicare"
DATA_EXTERNAL_MESH = ROOT / "data" / "external" / "mesh"
DATA_PROCESSED = ROOT / "data" / "processed"
REFERENCES_VOCAB = ROOT / "references" / "vocabularies"

MESH_DESCRIPTOR_XML = DATA_EXTERNAL_MESH / "desc2025.xml"

# Prefixos de TreeNumber do MeSH que definem cada tipo de entidade.
# Um descritor pode ter múltiplos TreeNumbers (aparecer em mais de um ramo);
# nesse caso ele é elegível para todos os tipos cujos prefixos batam.
MESH_BRANCH_RULES = {
    "symptom": {"include": ("C23",), "exclude": ()},
    "diagnosis": {"include": ("C",), "exclude": ("C23",)},
    "exam": {"include": ("E01",), "exclude": ()},
    "treatment": {"include": ("D", "E02"), "exclude": ()},
    "anatomical_site": {"include": ("A",), "exclude": ()},
}

GAZETTEER_FILES = {
    entity_type: REFERENCES_VOCAB / f"{entity_type}.csv"
    for entity_type in MESH_BRANCH_RULES
}

UNITS_FILE = REFERENCES_VOCAB / "units.txt"
TRIGGERS_FILE = REFERENCES_VOCAB / "triggers.csv"

# Distância de Damerau-Levenshtein aceita = floor(FUZZY_RATIO * len(sinônimo)).
FUZZY_RATIO = 0.15
FUZZY_MIN_LEN = 4  # abaixo disso, distância permitida vira 0 (equivalente a exato)

# Desempate quando um mesmo span casa (fuzzy) com mais de um tipo de entidade
# a uma distância igual: quem vem primeiro nesta lista ganha.
ENTITY_TYPE_PRIORITY = ["diagnosis", "symptom", "exam", "treatment", "anatomical_site"]

# Fuzzy é pra erro de digitação/variação local (ex. "heart-attack" vs
# "heart attack" — que já vira 1 token só no tokenizer, por incluir hífen na
# regex de palavra), não pra casar frase inteira parafraseada. Janela de 1
# palavra é suficiente pro caso de uso real e mantém o nº de candidatos por
# sentença baixo.
MAX_FUZZY_WINDOW_WORDS = 1

# Cap absoluto no raio de busca da BK-tree, independente da fórmula
# proporcional — mesmo com poda por desigualdade triangular, testado
# empiricamente: em dicionário médico (termos curtos, distâncias baixas e
# próximas entre si) uma BK-tree poda mal, e cada unidade de raio a mais
# multiplica MUITO o nº de nós visitados. Erros maiores que isso não são
# recuperados por fuzzy, só por exact match.
FUZZY_MAX_ABS_DISTANCE = 1

# Descritores MeSH genéricos demais pra virar entidade sozinhos — casam
# com palavra comum do inglês corrido ("a diagnosis of X", "therapeutics"
# como área/campo) em vez de referenciar uma entidade concreta do caso.
# Lista curada a partir de falsos positivos observados rodando o pipeline
# na amostra real; ajustar conforme mais casos forem revisados.
EXCLUDED_MESH_UI = {
    "D003933",  # Diagnosis (E01) — processo genérico, não um exame específico
    "D013812",  # Therapeutics (D/E02) — campo/área, não um tratamento específico
    "D004364",  # Pharmaceutical Preparations (D) — classe genérica de "droga"
}

# Fuzzy só roda nos gazetteers pequenos/médios. `diagnosis` (~55k sinônimos)
# e `treatment` (~100k, MeSH ramo D é majoritariamente nomenclatura química)
# são grandes demais pra BK-tree ficar rápida (medido: ~19ms/query, inviável
# em escala de milhares de sentenças) — ficam só com exact match, compensado
# pela cobertura já ampla de Entry Terms do MeSH nesses ramos.
FUZZY_ENTITY_TYPES = {"symptom", "exam", "anatomical_site"}
