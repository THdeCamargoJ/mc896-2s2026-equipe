# Projeto `NLP-Projeto 1`
# Project `NLP-Projeto 1`

> Equipe: `<Nome 1>`, `<Nome 2>`

## Slides

> Link para o PDF da apresentação (pasta `assets/slides/`).

## Metodologia

Pipeline 100% baseado em técnicas clássicas de NLP — sem modelo de
linguagem nesta etapa:

```
cases.csv → segmentação de sentenças → NER por gazetteer → valor/unidade → regras de relação → grafo (nós + arestas)
```

**1. Segmentação de sentenças** — regex simples (pontuação seguida de
maiúscula), sem tokenizador externo.

**2. NER por gazetteer** — fonte: [MeSH](https://www.nlm.nih.gov/mesh/)
(*Medical Subject Headings*), vocabulário médico público da NLM,
organizado em árvore por código (`TreeNumber`). O *descriptor file*
oficial (`desc2025.xml`) é filtrado por prefixo de código pra gerar os
dicionários. Cada descritor já vem com sinônimos prontos (*Entry Terms* —
variações de escrita do mesmo conceito, ex. "heart attack" = "myocardial
infarction"); mantemos só o termo preferido de cada conceito (atributo
`ConceptPreferredTermYN` do XML), o que reduz o dicionário ~4x sem perder
cobertura real de sinônimo.

Casamento contra o texto em duas fases:
- **Exato**, via **Aho-Corasick** — autômato que casa milhares de
  sinônimos contra a sentença numa só varredura (testar um `regex` por
  sinônimo não escala pra dicionários desse tamanho).
- **Fuzzy**, via **distância de Damerau-Levenshtein** (nº mínimo de
  edições — inserir, remover, substituir ou trocar posição de letras —
  pra transformar uma palavra na outra) indexada numa **BK-tree**
  (estrutura de busca que acha "palavras a distância X" sem comparar
  contra o dicionário inteiro). Cobre variação leve de escrita (ex.
  "heart-attack" vs "heart attack"). Só roda em Symptom/Exam/
  AnatomicalSite — em Diagnosis/Treatment o dicionário é grande demais
  pra essa busca ficar rápida (medido).

**3. Valor + unidade** — regex construído a partir de uma lista curada de
unidades (`units.txt`), sem fuzzy (erro aqui vira falso positivo fácil).
Reconhece também faixa de referência (`reference range X-Y`).

**4. Regras de relação** — co-ocorrência na mesma sentença + gatilho
textual (tabela na seção seguinte).

### Como cada entidade é extraída

| Entidade | Técnica | Como funciona |
|---|---|---|
| `Patient` | Colunas estruturadas | `age`/`gender` já vêm prontos em `cases.csv` — sem NLP |
| `Symptom` | Gazetteer MeSH (ramo `C23`), exato + fuzzy | Aho-Corasick + Damerau-Levenshtein/BK-tree |
| `Diagnosis` | Gazetteer MeSH (ramo `C`, exceto `C23`), só exato | fuzzy desativado — dicionário grande demais |
| `Exam` | Gazetteer MeSH (ramo `E01`), exato + fuzzy | igual Symptom |
| `Treatment` | Gazetteer MeSH (ramos `D`+`E02`), só exato | igual Diagnosis |
| `AnatomicalSite` | Gazetteer MeSH (ramo `A`), exato + fuzzy | igual Symptom |
| `ExamResult` | Regex de valor+unidade | número+unidade logo após um `Exam` |
| `Finding` | Gatilho textual (fallback) | sem valor numérico: texto perto do `Exam` após um gatilho ("showed"/"confirmed"/"excluded"...) que não bate com nenhum vocabulário |
| `History` | Gatilho "history of" + reclassificação | Diagnosis/Symptom/Treatment mencionado após o gatilho vira histórico, não caso atual |
| `Unit` | Lista curada manual, sem fuzzy | extraída junto do valor via regex |

Regras de relação entre entidades:

| Padrão no texto | Relação criada |
|---|---|
| Substância (ramo `D`) com valor logo depois, sem gatilho de administração | `Treatment` → reclassificado como `Exam` (ex. "Hemoglobin 9 g/dL" não é tratamento) |
| Symptom/ExamResult + Diagnosis na mesma sentença | `SUPPORTS` |
| Treatment após um Diagnosis | `TREATED_BY` |
| AnatomicalSite + Diagnosis/Exam/Treatment na mesma sentença | `LOCATED_IN`/`PERFORMED_ON`/`TARGETS` |

Código completo em [`src/kg_extraction/`](src/kg_extraction/) ([instruções de instalação/execução](src/README.md)).

## Modelo Lógico

Grafo em duas tabelas (`node_id`/`case_id`/`type`/`label`/`attributes` e
`edge_id`/`case_id`/`source_id`/`target_id`/`relation`/`attributes`).

**Tipos de nó**: `Patient`, `History`, `Symptom`, `Exam`, `ExamResult`,
`Finding`, `Treatment`, `AnatomicalSite`, `Unit`.

**Relações**: `HAS_HISTORY`, `PRESENTS_WITH`, `UNDERWENT_EXAM`,
`UNDERWENT_TREATMENT`, `HAS_RESULT`, `HAS_UNIT`, `DIAGNOSED_WITH`,
`SUPPORTS`, `TREATED_BY`, `CONFIRMS`/`EXCLUDES`/`REVEALS`,
`LOCATED_IN`/`TARGETS`/`PERFORMED_ON`. `Unit` é compartilhado entre casos
(mesma unidade sempre aponta pro mesmo nó).

Valor e faixa de referência ficam como texto em `attributes` do
`ExamResult` — não viram nó próprio (decomposição mínima o suficiente
pras análises propostas, sem inflar o grafo).

> Não modelamos `VocabConcept`/`SAME_AS` (link entidade→código MeSH):
> testado e removido — quase dobrava nós/arestas do grafo sem agregar
> valor num grafo básico.

> Coloque aqui a imagem do modelo lógico (ver [modelo de
> base](https://docs.google.com/presentation/d/10RN7bDKUka_Ro2_41WyEE76Wxm4AioiJOrsh6BRY3Kk/edit?usp=sharing))
> em `assets/images/modelo-logico-grafos.png`.

## Análises que podem ser realizadas

- Cruzar `major_mesh_terms` de `metadata.csv` com `Diagnosis`/`Symptom`
  extraídos (ambos vêm de MeSH) para validar contra anotação externa.
- Medir cobertura do gazetteer (sentenças sem nenhuma entidade) pra
  achar lacunas da taxonomia MeSH.
- Comparar precisão Symptom vs. Diagnosis — o ramo `C23` do MeSH tem uma
  subárvore "Chronic Disease" que cross-lista doenças específicas como
  se fossem sintomas.
- `Exam`s que mais co-ocorrem com cada `Diagnosis`, sugerindo protocolos
  diagnósticos recorrentes.

## Ferramentas

- **Python** (pandas).
- Técnicas clássicas de NLP from-scratch: regex, gazetteer com
  Aho-Corasick + Damerau-Levenshtein/BK-tree, regras de relação — sem
  bibliotecas de NER estatístico/neural, conforme exigido nesta etapa.
- **MeSH (NLM)** como vocabulário controlado — público, sem
  licença/cadastro (ao contrário de UMLS/SNOMED CT).
- Estrutura de projeto: [Cookiecutter Data Science](https://drivendata.github.io/cookiecutter-data-science/) (template padrão pra organizar projetos de dados), simplificada.

## Resultados

Pipeline rodado sobre os **56 casos / 50 artigos** da amostra oficial
(`data/raw/multicare/cases.csv` — o enunciado cita "246 casos", mas o
arquivo de amostra distribuído tem 56 linhas reais; `metadata.csv` bate
com "50 artigos"). ~2 minutos de processamento.

**Nós** (1593 total): AnatomicalSite 399, Exam 274, Treatment 249,
Symptom 237, Diagnosis 137, ExamResult 91, Finding 89, Patient 56,
History 43, Unit 18.

**Arestas** (2057 total): UNDERWENT_EXAM 274, UNDERWENT_TREATMENT 249,
PRESENTS_WITH 237, PERFORMED_ON 216, TARGETS 197, TREATED_BY 179,
LOCATED_IN 173, DIAGNOSED_WITH 137, REVEALS 93, HAS_RESULT 91,
HAS_UNIT 91, SUPPORTS 58, HAS_HISTORY 43, CONFIRMS 15, EXCLUDES 4.

> Capturas de tela da visualização em `assets/images/`.

### Limitações conhecidas

Usar MeSH sozinho (em vez de UMLS/SNOMED CT/RxNorm combinados)
simplificou a implementação, mas sua árvore não bate 1:1 com nossos
tipos de entidade:

- **Ramo `C23`** é mais largo que "sintoma": tem subárvore "Chronic
  Disease" que lista doenças específicas — algumas entidades que
  deveriam ser `Diagnosis` saem como `Symptom`.
- **Corpos/fluidos caem em `AnatomicalSite`**: "serum", "tail" batem
  certo com a árvore, mas fora do sentido clínico do texto.
- **Cobertura de `Exam` tem buracos**: nem todo exame comum tem
  descritor MeSH isolado (ex. "endoscopic ultrasound" sozinho não bate).
- **Ambiguidade residual em `Treatment`**: a reclassificação pra Exam só
  funciona quando o valor está adjacente no texto.
- **Termos genéricos além dos 3 já filtrados** (`EXCLUDED_MESH_UI` em
  `config.py`): lista curada à mão, não exaustiva.
- **`AnatomicalSite` só liga a algo por co-ocorrência na sentença**: ~49%
  dos 399 nós ainda ficam sem aresta (menção solta, sem outra entidade
  na mesma sentença) — regra de proximidade textual, não relação
  semântica de verdade.

## Como Modelos de Linguagem foram Usados

Conforme o enunciado, **nenhum LLM foi usado na etapa de extração do
grafo** (NER, valores e relações são 100% regras/dicionário/regex — ver
`src/kg_extraction/features/`).

Modelos de linguagem foram usados apenas para:
- Apoiar o design e implementação da **aplicação web de visualização**,
  que o enunciado libera explicitamente para uso de IA;
- `<a equipe deve completar aqui outros usos, ex.: revisão de texto, geração
  de rascunho dos slides, etc.>`

## Referências Bibliográficas

- Nievas Offidani, M., Roffet, F., González Galtier, M. C., Massiris, M., &
  Delrieux, C. (2025). An Open-Source Clinical Case Dataset for Medical Image
  Classification and Multimodal AI Applications. *Data*, 10(8), 123.
  https://doi.org/10.3390/DATA10080123
- Ji, S., Pan, S., Cambria, E., Marttinen, P., & Yu, P. S. (2022). A Survey on
  Knowledge Graphs: Representation, Acquisition, and Applications. *IEEE
  Transactions on Neural Networks and Learning Systems*, 33(2), 494–514.
  https://doi.org/10.1109/TNNLS.2021.3070843
- Lowrance, R., & Wagner, R. A. (1975). An Extension of the
  String-to-String Correction Problem. *Journal of the ACM*, 22(2), 177–183.
- `<demais referências da equipe>`
