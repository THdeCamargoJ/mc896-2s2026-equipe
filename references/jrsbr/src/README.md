# Instalação e execução

## Dependências

```
pip install -r ../requirements.txt
```

Só `pandas` — o resto (regex, XML, CSV) é biblioteca padrão do Python.

## 1. Gazetteers (só na primeira vez, ou se trocar de ano do MeSH)

Baixa `desc2025.xml` (~314MB) em `data/external/mesh/` (ver
`https://nlmpubs.nlm.nih.gov/projects/mesh/2025/xmlmesh/desc2025.gz`),
descompacta, e roda:

```
PYTHONPATH=. python3 -m kg_extraction.vocab.mesh_parser
```

Gera os 5 CSVs de `references/vocabularies/` (`symptom.csv`,
`diagnosis.csv`, `exam.csv`, `treatment.csv`, `anatomical_site.csv`).

## 2. Rodar o pipeline completo

```
PYTHONPATH=. python3 -m kg_extraction.run_pipeline
```

Lê `data/raw/multicare/cases.csv`, escreve `data/processed/nodes.csv` e
`data/processed/edges.csv`. Primeira execução monta e cacheia os
gazetteers (~25s, cache em `data/interim/gazetteer_cache/`); nas
seguintes só carrega o cache.

Opções:

```
--limit N                     processa só os N primeiros casos (debug rápido)
--force-rebuild-gazetteers    ignora o cache e remonta do zero
```

Exemplo pra testar rápido antes de rodar tudo:

```
PYTHONPATH=. python3 -m kg_extraction.run_pipeline --limit 10
```

## Estrutura do código

```
kg_extraction/
  config.py                        caminhos e constantes (thresholds, prefixos MeSH, etc.)
  vocab/
    mesh_parser.py                 desc2025.xml -> 5 CSVs de gazetteer
    gazetteer_cache.py             cache em disco dos gazetteers montados
  features/
    preprocessing.py               segmentação de sentenças
    gazetteer_ner.py                NER exato (Aho-Corasick) + fuzzy (BK-tree)
    aho_corasick.py                 autômato multi-padrão
    damerau_levenshtein.py          distância de edição + BK-tree
    value_unit_extraction.py        regex de valor+unidade
    triggers.py                     gatilhos textuais (history/exam_result/administration)
    relations.py                    reclassificação Treatment->Exam, History, ExamResult/Finding
  graph/
    canonical_graph.py              monta nós/arestas por caso
  run_pipeline.py                   ponto de entrada
```
