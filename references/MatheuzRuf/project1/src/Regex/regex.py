import re
import math

interpretacoes = [
    ##Gerado por IA
    # Normalidade
    "normal",
    "abnormal",
    "within normal limits",
    "WNL",
    "within normal range",
    "within reference range",
    "outside normal limits",
    "outside normal range",
    "outside reference range",
    "out of range",
    "positive",
    "pos",
    "negative",
    "neg",

    # Elevado
    "elevated",
    "high",
    "increased",
    "raised",
    "above normal",
    "above normal range",
    "above reference range",
    "above reference limit",
    "above upper limit",
    "higher than normal",
    "greater than normal",
    "excessive",

    # Reduzido
    "low",
    "decreased",
    "reduced",
    "lowered",
    "diminished",
    "below normal",
    "below normal range",
    "below reference range",
    "below reference limit",
    "below lower limit",
    "lower than normal",
    "less than normal",
    "deficient",

    # Intensidade genérica
    "slight",
    "slightly",
    "mild",
    "mildly",
    "moderate",
    "moderately",
    "marked",
    "markedly",
    "significant",
    "significantly",
    "substantial",
    "substantially",
    "severe",
    "severely",
    "extreme",
    "extremely",
    "profound",
    "profoundly",

    # Intensidade + elevação
    "slightly elevated",
    "mildly elevated",
    "moderately elevated",
    "markedly elevated",
    "significantly elevated",
    "substantially elevated",
    "severely elevated",
    "extremely elevated",
    "profoundly elevated",

    "slightly increased",
    "mildly increased",
    "moderately increased",
    "markedly increased",
    "significantly increased",
    "substantially increased",
    "severely increased",
    "extremely increased",
    "profoundly increased",

    "slightly high",
    "mildly high",
    "moderately high",
    "markedly high",
    "significantly high",
    "severely high",
    "extremely high",
    "profoundly high",

    "slightly raised",
    "mildly raised",
    "moderately raised",
    "markedly raised",
    "significantly raised",
    "severely raised",
    "extremely raised",

    # Intensidade + redução
    "slightly low",
    "mildly low",
    "moderately low",
    "markedly low",
    "significantly low",
    "severely low",
    "extremely low",
    "profoundly low",

    "slightly decreased",
    "mildly decreased",
    "moderately decreased",
    "markedly decreased",
    "significantly decreased",
    "substantially decreased",
    "severely decreased",
    "extremely decreased",
    "profoundly decreased",

    "slightly reduced",
    "mildly reduced",
    "moderately reduced",
    "markedly reduced",
    "significantly reduced",
    "substantially reduced",
    "severely reduced",
    "extremely reduced",
    "profoundly reduced",

    "slightly diminished",
    "mildly diminished",
    "moderately diminished",
    "markedly diminished",
    "significantly diminished",
    "severely diminished",
    "extremely diminished",

    # Limítrofe
    "borderline",
    "borderline high",
    "borderline elevated",
    "borderline increased",
    "borderline low",
    "borderline decreased",
    "borderline abnormal",
    "near upper limit",
    "near lower limit",

    # Quantidade semiquantitativa
    "trace",
    "minimal",
    "small",
    "little",
    "few",
    "moderate",
    "marked",
    "large",
    "substantial",
    "abundant",
    "numerous",
    "massive",

    # Frequência / ocorrência quantitativa
    "rare",
    "occasional",
    "scattered",
    "few",
    "several",
    "multiple",
    "numerous",
    "many",
    "frequent",
    "abundant",

    # Tendência quantitativa
    "increasing",
    "decreasing",
    "rising",
    "falling",
    "stable",
    "unchanged",
    "persistent",
    "persistently elevated",
    "persistently increased",
    "persistently high",
    "persistently low",
    "persistently decreased",
    "persistently reduced",

    # Mudança em relação a medida anterior
    "improved",
    "worsened",
    "increased",
    "decreased",
    "normalized",
    "normalizing",
    "returned to normal",
    "remained elevated",
    "remained high",
    "remained low",
    "remained increased",
    "remained decreased",
    "remained stable",

    # Comparação com limite
    "above threshold",
    "below threshold",
    "above cutoff",
    "below cutoff",
    "within threshold",
    "within cutoff",
    "exceeds threshold",
    "exceeded threshold",
    "exceeds cutoff",

    # Valores extremos
    "critical",
    "critically high",
    "critically low",
    "dangerously high",
    "dangerously low",
    "severely abnormal",
]

interpretacoes_ordenadas = sorted(interpretacoes, key=len, reverse=True)

regex_interpretacoes = (
    r"\b(?:"
    + "|".join(re.escape(x) for x in interpretacoes_ordenadas)
    + r")\b"
)

inteiro = r"(\d+[%]|\d+\s?[^\s.,!?;:]+)"
rangeInteiro = r"(\d+[-]\d+[%]|\d+[-]\d+\s?[^\s.,!?;:]+)"

decimal = r"(\d+\.\d+[%]|\d+\.\d+\s?[^\s.,!?;:]+)"
rangeDecimal = r"(\d+\.\d+[-]\d+\.\d+[%]|\d+\.\d+[-]\d+\.\d+\s?[^\s.,!?;:]+)"

padraoFinal = r"\d+(?:\,\d+)?(?:\.\d+)?(?:\s?-\s?\d+(?:\.\d+)?)?(?:%|\s?[^\s.,!?;:)\]}]+)"
valor = r"\d+(?:\,\d+)?(?:\.\d+)?(?:\s?-\s?\d+(?:\.\d+)?)?"

def extract_measurements(texto, entities):
    resultado = []
    mentions = []

    exam_findings = [
    entity
    for entity in entities
    if entity.type in {"Exam", "Finding"}
    ]

    for entity in exam_findings:
        for start, end in entity.positions:
            mentions.append([entity, start+(end-start)/2])

    for match in re.finditer(padraoFinal, texto):
        numero = re.search(valor, match.group())
        unidade = match.group()[numero.end():].strip()
        value = math.inf
        reference = None
        for mention in mentions:
            newvalue = abs(match.start()-mention[1])
            if (newvalue < value):
                value = newvalue
                reference = mention[0]
        resultado.append([match.group(), numero.group(), unidade, reference])

    for match in re.finditer(regex_interpretacoes, texto):
            value = math.inf
            reference = None
            for mention in mentions:
                newvalue = abs(match.start()-mention[1])
                if (newvalue < value):
                    value = newvalue
                    reference = mention[0]
            resultado.append([match.group(), None, None, reference])

    return resultado
