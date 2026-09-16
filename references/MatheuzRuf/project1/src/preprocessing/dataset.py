import csv
from pathlib import Path

from src.preprocessing.text import PreprocessedText, preprocess_text


def load_cases(path: str | Path) -> list[dict]:
    """
    Lê cases.csv e retorna uma lista de casos.
    """

    path = Path(path)

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader)


def preprocess_cases(path: str | Path) -> list[dict]:
    """
    Lê cases.csv e adiciona os resultados do preprocessing.

    O case_text original permanece intacto.
    """

    cases = load_cases(path)

    processed_cases = []

    for case in cases:
        result: PreprocessedText = preprocess_text(case["case_text"])

        processed_case = {
            **case,

            # Texto original
            "original_text": result.original,

            # Para inspeção/debug
            "normalized_text": result.normalized,

            # Tokens completos
            "tokens": result.tokens,

            # Para retrieval
            "retrieval_tokens": result.retrieval_tokens,
        }

        processed_cases.append(processed_case)

    return processed_cases