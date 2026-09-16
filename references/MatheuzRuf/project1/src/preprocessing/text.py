import re
import unicodedata
from dataclasses import dataclass


# Stopwords básicas para textos clínicos em inglês.
# Mantemos uma lista explícita para não adicionar dependências externas.
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being",
    "but", "by", "for", "from", "had", "has", "have", "he", "her",
    "hers", "him", "his", "i", "if", "in", "into", "is", "it",
    "its", "itself", "me", "my", "of", "on", "or", "our", "ours",
    "she", "so", "that", "the", "their", "theirs", "them", "they",
    "this", "those", "to", "was", "we", "were", "what", "when",
    "where", "which", "who", "whom", "with", "you", "your", "yours"
}


@dataclass
class PreprocessedText:
    """
    Resultado do preprocessing de um clinical case.

    original:
        Texto original, preservado para extraction.

    normalized:
        Texto normalizado, mas ainda legível.

    tokens:
        Tokens produzidos a partir do texto normalizado.

    retrieval_tokens:
        Tokens sem stopwords, destinados a retrieval.
    """

    original: str
    normalized: str
    tokens: list[str]
    retrieval_tokens: list[str]


def normalize_text(text: str) -> str:
    """
    Normaliza o texto sem remover informação clínica.

    Operações:
    - Unicode normalization (NFKC)
    - normalização de aspas/apóstrofos
    - normalização de alguns tipos de hífen
    - normalização de espaços
    - lowercase
    """

    # Unicode compatibility normalization.
    text = unicodedata.normalize("NFKC", text)

    # Normaliza diferentes tipos de aspas/apóstrofos.
    text = text.replace("“", '"')
    text = text.replace("”", '"')
    text = text.replace("‘", "'")
    text = text.replace("’", "'")

    # Normaliza diferentes tipos de hífen/dash.
    text = re.sub(r"[‐-‒–—−]", "-", text)

    # Normaliza espaços, tabs e quebras de linha.
    text = re.sub(r"\s+", " ", text)

    # Para retrieval, usamos lowercase.
    text = text.lower().strip()

    return text


def tokenize(text: str) -> list[str]:
    """
    Tokeniza texto clínico preservando números, unidades e expressões
    relevantes.

    Exemplos preservados:

        850 U/L       -> ["850", "u/l"]
        96 mg/L       -> ["96", "mg/l"]
        5-day         -> ["5-day"]
        4 cm          -> ["4", "cm"]
        92%           -> ["92%"]

    Também preserva palavras com hífen.
    """

    # Ordem dos padrões é importante.
    token_pattern = re.compile(
        r"""
        \d+(?:\.\d+)?%                  # 92%, 12.5%
        |
        \d+(?:\.\d+)?(?:-\w+)?          # 5-day, 4, 850, 12.5
        |
        [a-zA-Z]+(?:/[a-zA-Z]+)+         # U/L, mg/L, kg/m2
        |
        [a-zA-Z]+(?:-[a-zA-Z]+)*         # palavras e palavras-com-hífen
        |
        [<>]=?                           # <, >, <=, >=
        |
        [+-]\d+(?:\.\d+)?                # +5, -2.5
        """,
        re.VERBOSE,
    )

    return token_pattern.findall(text)


def remove_stopwords(tokens: list[str]) -> list[str]:
    """
    Remove stopwords sem remover números ou unidades.

    Stopwords são removidas apenas quando o token inteiro corresponde
    a uma stopword.
    """

    return [
        token
        for token in tokens
        if token not in STOPWORDS
    ]


def preprocess_text(text: str) -> PreprocessedText:
    """
    Executa o pipeline completo de preprocessing.

    O texto original é preservado integralmente.
    """

    original = text

    normalized = normalize_text(text)

    tokens = tokenize(normalized)

    retrieval_tokens = remove_stopwords(tokens)

    return PreprocessedText(
        original=original,
        normalized=normalized,
        tokens=tokens,
        retrieval_tokens=retrieval_tokens,
    )