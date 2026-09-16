# Projeto de extração de informação e construção de grafo clínico — V1

Baseline de extração clássica para os casos clínicos do MultiCaRe, organizado
conforme o template da disciplina:

```text
data/          dados brutos, intermediários e processados
pipelines/     notebooks e workflows
src/           código Python
assets/        imagens e slides
```

## Objetivo

Extrair entidades e relações clínicas de `cases.csv` e gerar duas tabelas por
caso: `nodes.csv` e `edges.csv`. A V1 é um baseline interpretável para as
comparações futuras; ela não utiliza LLMs, ATNs ou Datomic.

## Dados

- `data/raw/cases.csv`: texto, idade e gênero dos casos clínicos.
- `data/raw/metadata.csv`: metadados dos artigos de origem.
- `data/external/data_dictionary.csv`: documentação dos campos do dataset.

O texto de `case_text` é a fonte principal da extração. `age` e `gender` são
usados para o nó do paciente. O `article_id` mantém a ligação com os metadados
do artigo.

## Pipeline da V1

```text
cases.csv
 -> segmentação simples em sentenças
 -> correspondência lexical por regex no léxico tipado
 -> regras locais de negação
 -> regex para valores e unidades
 -> criação dos nós
 -> criação das arestas
 -> nodes.csv e edges.csv
```

O léxico é manual, pequeno e separado por categoria em
`src/clinical_kg/lexicons/`. Cada arquivo contém `surface_form` e
`normalized_label`; o nome do arquivo define o tipo da entidade.

As categorias atuais são `Symptom`, `History`, `Diagnosis`, `Exam`,
`Treatment` e `AnatomicalSite`. As relações iniciais incluem `PRESENTS_WITH`,
`HAS_HISTORY`, `UNDERWENT_EXAM`, `DIAGNOSED_WITH`, `TREATED_BY` e
`LOCATED_IN`.

Cada nó e aresta preserva o `case_id`, a evidência textual e, quando aplicável,
o número da sentença. Atributos estruturados são serializados em JSON na
coluna `attributes`.

## Execução

Na raiz de `project1`:

```bash
PYTHONPATH=src python -m clinical_kg.pipeline
```

Opções:

```bash
PYTHONPATH=src python -m clinical_kg.pipeline \
 --cases data/raw/cases.csv \
 --lexicons src/clinical_kg/lexicons \
 --output data/processed
```

Saídas:

```text
data/processed/nodes.csv
data/processed/edges.csv
```

Para gerar a visualização HTML separadamente:

```bash
PYTHONPATH=src python -m clinical_kg.visualize
```

Abra `data/processed/graph.html` em um navegador. A página permite selecionar
um caso e clicar em nós ou arestas para consultar atributos e evidências.

## Escopo e limitações conhecidas

Esta versão não possui tokenização formal, POS tagging, segmentação robusta
de abreviações, vocabulário biomédico externo, associação completa
entre exames e resultados/achados ou persistência em Datomic. A visualização
HTML existente é simples e independente do armazenamento; a V1 serve como
referência para medir o efeito das versões posteriores.

## Organização das versões

A V1 permanece preservada neste diretório. As versões posteriores serão
desenvolvidas independentemente em diretórios irmãos:

```text
project1-v2
project1-v3
project1-v4
```
