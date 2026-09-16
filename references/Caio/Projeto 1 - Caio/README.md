# Projeto 1 — comparação das versões V1–V4

Este diretório contém quatro implementações independentes para extração de
informação clínica dos casos do MultiCaRe e construção de grafos em duas
tabelas: `nodes.csv` e `edges.csv`. Este documento cobre apenas a linha ativa de
desenvolvimento.

## Fluxo comum

```text
cases.csv
  -> reconhecimento de entidades
  -> normalização
  -> extração de contexto e relações
  -> nodes.csv e edges.csv
  -> graph.html
```

Os léxicos são arquivos CSV separados por categoria. Uma entrada lexical
associa uma forma encontrada no texto a um rótulo normalizado; o arquivo em
que ela aparece define o tipo do nó. Por exemplo:

```csv
surface_form,normalized_label
coughing,cough
```

produz uma menção `coughing`, normalizada como `cough`, do tipo `Symptom`
quando está em `symptoms.csv`.

## V1 — baseline

A V1 usa os léxicos manuais com duas colunas:

```text
surface_form,normalized_label
```

O pipeline segmenta o texto de forma simples e cria uma expressão regular
literal para cada `surface_form`. As ocorrências encontradas são classificadas
pelo arquivo lexical e normalizadas pelo `normalized_label`. Regex adicionais
identificam valores, unidades e marcadores simples de negação.

A V1 não possui tokenização formal nem POS. Suas relações são baseadas em
regras locais, como sintomas presentes ou negados, exames, diagnósticos,
tratamentos, histórico e regiões anatômicas.

## V2 — tokenização e POS heurístico

A V2 mantém o reconhecimento lexical por regex da V1, mas adiciona:

- tokenização explícita por regex;
- POS heurístico baseado em regras;
- `findings.csv` e o tipo `Finding`;
- relações entre exames e achados usando verbos relacionais;
- relações `REVEALS`, `CONFIRMS` e `EXCLUDES`.

O POS é evidência auxiliar. Ele não substitui o léxico para classificar uma
entidade como `Exam`, `Finding` ou outro tipo.

## V3 — léxico enriquecido

A V3 mantém o algoritmo clássico da V2: tokenização, POS heurístico,
correspondência lexical por regex, regras de contexto e relações. A mudança
principal está no formato dos léxicos:

```text
surface_form,normalized_label,source,ontology,code
```

Isso permite registrar sinônimos, abreviações, normalização e proveniência.
Os campos de ontologia e código estão preparados para fontes externas, mas as
entradas atuais foram curadas manualmente e não resultam de uma consulta
automática a MeSH, LOINC, UMLS ou outra ontologia.

Os metadados lexicais são preservados nos atributos dos nós.

## V4 — V3 com medspaCy

A V4 mantém o léxico enriquecido e as regras da V3, mas substitui a busca
lexical por regex pelo `TargetMatcher` do medspaCy:

```text
CSV lexical
  -> TargetRule para cada surface_form
  -> TargetMatcher encontra as menções
  -> pipeline recupera normalização e metadados
  -> regras próprias criam relações e o grafo
```

O `TargetMatcher` é usado para reconhecimento lexical. A negação continua
sendo identificada por regex própria, o POS continua heurístico, os valores e
unidades continuam sendo extraídos por regex e as relações continuam sendo
geradas pelo código do projeto. A V4 usa os offsets reais das menções para
identificar verbos entre exames e achados.

## Comparação

| Aspecto | V1 | V2 | V3 | V4 |
|---|---|---|---|---|
| Reconhecimento | Regex lexical | Regex lexical | Regex lexical | medspaCy `TargetMatcher` |
| Tokenização | Aproximada | Regex explícita | Mantida | Mantida + spaCy/medspaCy |
| POS | Não | Heurístico | Heurístico | Heurístico |
| Léxico | Manual, 2 colunas | Manual, 2 colunas | Manual enriquecido, 5 colunas | Igual à V3 |
| `Finding` | Não | Sim | Sim | Sim |
| Proveniência lexical | Não estruturada | Não estruturada | `source` | `source` |
| Ontologia/código | Não | Não | Campos preparados | Campos preparados |
| Relações exame-achado | Limitadas | Regras explícitas | Mantidas | Mantidas com reconhecimento medspaCy |
| LLM na extração | Não | Não | Não | Não |
| Datomic | Não | Não | Não | Não |

## Artefatos atuais

Cada versão ativa possui:

```text
data/processed/nodes.csv
data/processed/edges.csv
data/processed/graph.html
```

Os artefatos regenerados com os léxicos atuais são:

| Versão | Nós | Arestas |
|---|---:|---:|
| V1 | 876 | 820 |
| V2 | 973 | 830 |
| V3 | 1064 | 841 |
| V4 | 1064 | 842 |

As diferenças de quantidade refletem tanto o mecanismo de reconhecimento
quanto a cobertura dos léxicos. V3 e V4 possuem a mesma quantidade de nós
neste corpus porque o `TargetMatcher` reconheceu as mesmas menções que a
regex da V3; isso não significa que os mecanismos sejam iguais.

## Limitações e escopo

As versões não implementam Datomic nem uma avaliação anotada de precisão,
revocação e F1. A visualização HTML é independente do armazenamento e apenas
lê as tabelas CSV processadas. A construção dos léxicos atuais foi manual,
com assistência de curadoria, e deve ser documentada separadamente da
extração clássica executada pelos pipelines.
