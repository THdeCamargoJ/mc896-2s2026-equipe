# Projeto de extração de informação e construção de grafo clínico — V2

A V2 mantém o baseline lexical da V1 e acrescenta tokenização explícita e
etiquetagem Part-of-Speech (POS) baseada em regras. Ela é uma implementação
independente em relação a `project1`.

## Pipeline

```text
case_text
  -> segmentação em sentenças
  -> tokenização por regex
  -> POS tagging baseado em regras
  -> correspondência exata no léxico
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
estatísticos externos. O POS inferido é armazenado nos atributos dos nós para
permitir auditoria.

Os léxicos continuam sendo arquivos manuais com duas colunas:

```text
surface_form,normalized_label
```

O arquivo `findings.csv` acrescenta a categoria `Finding`. A forma encontrada
é normalizada pelo segundo campo, enquanto o tipo é definido pelo arquivo
lexical.

## Execução

Na raiz de `project1-v2`:

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
navegador. Os elementos do grafo exibem evidência e atributos ao serem
selecionados.

É possível selecionar outros caminhos:

```bash
PYTHONPATH=src python -m clinical_kg.pipeline \
  --cases data/raw/cases.csv \
  --lexicons src/clinical_kg/lexicons \
  --output data/processed
```

## Escopo

Esta versão não implementa vocabulários externos, ATN ou Datomic.
A visualização HTML é um artefato separado que lê `nodes.csv` e `edges.csv`.
A V1 permanece preservada em `../project1`; não altere seus arquivos ao
trabalhar nesta versão.
