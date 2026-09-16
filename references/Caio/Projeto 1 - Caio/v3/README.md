# Projeto de extração de informação e construção de grafo clínico — V3

A V3 mantém o pipeline lexical e o POS da V2 e acrescenta um léxico enriquecido
com sinônimos, abreviações, normalização e metadados de proveniência. Ela é uma
implementação independente em relação a `project1` e `project1-v2`.

## Pipeline

```text
case_text
  -> segmentação em sentenças
  -> tokenização por regex
  -> POS tagging baseado em regras
  -> correspondência exata no léxico ampliado
  -> normalização e metadados lexicais
  -> regex para valores e unidades
  -> regras de contexto
  -> relações com padrões POS + verbos relacionais
  -> nodes.csv e edges.csv
```

O POS é usado como evidência auxiliar, não como classificador clínico:
o léxico define que um termo é `Exam` ou `Finding`, enquanto o POS ajuda a
reconhecer a estrutura de relações como:

```text
[Exam] + showed/revealed/demonstrated + [Finding]
```

Isso pode gerar, por exemplo:

```text
Exam --REVEALS--> Finding
Exam --CONFIRMS--> Finding
Exam --EXCLUDES--> Finding
```

O tagger é deliberadamente baseado em regras e não usa LLM nem modelos
estatísticos externos. O POS inferido é armazenado nos atributos dos
nós para permitir auditoria.

## Léxico enriquecido

Os arquivos em `src/clinical_kg/lexicons/` possuem as colunas:

```text
surface_form,normalized_label,source,ontology,code
```

`surface_form` é a expressão encontrada no texto; `normalized_label` é o
rótulo usado no grafo; `source` registra a origem do termo; e `ontology` e
`code` são campos opcionais para futuras entradas MeSH, UMLS, SNOMED CT,
LOINC, ICD-10 ou RxNorm. As entradas atuais são explicitamente marcadas como
`manual`; nenhum código externo foi inventado ou preenchido sem validação.

O tipo do nó continua sendo definido pelo arquivo lexical. Dessa forma, os
metadados de vocabulário enriquecem a entidade sem alterar a separação entre
`Symptom`, `Diagnosis`, `Exam`, `Finding`, `Treatment`, `History` e
`AnatomicalSite`.

## Execução

Na raiz de `project1-v3`:

```bash
PYTHONPATH=src python -m clinical_kg.pipeline
```

Saídas:

```text
data/processed/nodes.csv
data/processed/edges.csv
```

## Visualização

Gere uma visualização HTML simples a partir das tabelas:

```bash
PYTHONPATH=src python -m clinical_kg.visualize
```

O arquivo `data/processed/graph.html` pode ser aberto diretamente no
navegador. Os nós mostram atributos lexicais, incluindo POS e metadados de
fonte quando presentes.

É possível selecionar outros caminhos:

```bash
PYTHONPATH=src python -m clinical_kg.pipeline \
  --cases data/raw/cases.csv \
  --lexicons src/clinical_kg/lexicons \
  --output data/processed
```

## Escopo

Esta versão não implementa correspondência aproximada, ATN ou Datomic. A
visualização HTML é um artefato separado que lê as tabelas
processadas. Os campos `ontology` e `code` estão preparados para fontes
externas validadas, mas as entradas atuais são manuais. A V1 permanece
preservada em `../project1` e a V2 em `../project1-v2`; não altere esses
diretórios ao trabalhar nesta versão.
