# Projeto de extração de informação e construção de grafo clínico — V4

A V4 mantém o léxico enriquecido, a tokenização, o POS e as regras da V3,
mas utiliza o `TargetMatcher` do medspaCy para aplicar o reconhecimento
lexical baseado em regras. Ela é independente das versões anteriores.

## Pipeline

```text
case_text
  -> segmentação em sentenças
  -> medspaCy TargetMatcher + léxico enriquecido
  -> tokenização por regex e POS baseado em regras
  -> normalização e metadados lexicais
  -> regex para valores e unidades
  -> regras de contexto
  -> relações com padrões POS + verbos relacionais
  -> nodes.csv e edges.csv
```

O medspaCy fornece a infraestrutura de reconhecimento, mas os termos, tipos e
rótulos continuam vindo dos arquivos em `src/clinical_kg/lexicons/`. Não há
LLM ou modelo estatístico externo na V4.

O `TargetMatcher` recebe uma `TargetRule` para cada `surface_form` dos
léxicos. Ele encontra a menção e fornece seus offsets; a normalização,
negação, POS, valores, unidades e relações continuam sendo tratados pelo
código do projeto. A V4 usa os offsets reais das menções ao procurar verbos
relacionais entre exames e achados.

## Requisitos e execução

Instale o medspaCy:

```bash
pip install medspacy
```

Na raiz de `project1-v4`:

```bash
PYTHONPATH=src python -m clinical_kg.pipeline \
  --lexicons src/clinical_kg/lexicons
```

Saídas:

```text
data/processed/nodes.csv
data/processed/edges.csv
```

A visualização HTML pode ser gerada com:

```bash
PYTHONPATH=src python -m clinical_kg.visualize
```

O arquivo `data/processed/graph.html` é independente do medspaCy e pode ser
aberto diretamente no navegador.

## Escopo

A V4 não implementa ATN ou Datomic. O medspaCy aplica regras de reconhecimento
lexical por meio do `TargetMatcher`; negação, POS e relações
clínicas continuam sendo tratados pelas regras do projeto. As versões V1, V2
e V3 permanecem preservadas.
