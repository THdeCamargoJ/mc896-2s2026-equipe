import csv
import os
import re
from pathlib import Path

# Estrutura de diretórios
DATA_DIR = Path("Dados")
CASES_FILE = DATA_DIR / "cases.csv"
NORMALIZED_FILE = DATA_DIR / "casesNormalizado.csv"
DICT_FILE = DATA_DIR / "dicionario_ingles.csv"
POS_FILE = DATA_DIR / "partOfSpeech.csv"

# Regex para unidades de medida médicas comuns
UNITS_REGEX = r"(?:mg|g|kg|ml|l|mcg|mmol/l|mg/dl|cm|mm|mmhg|bpm|°c|°f|u/l|iu|meq|%)"

# Regras de expansão de contrações em inglês
CONTRACTIONS = [
    (re.compile(r"\bcan't\b", re.IGNORECASE), "can not"),
    (re.compile(r"\bwon't\b", re.IGNORECASE), "will not"),
    (re.compile(r"\bshan't\b", re.IGNORECASE), "shall not"),
    (re.compile(r"(\b\w+)n't\b", re.IGNORECASE), r"\1 not"),
    (re.compile(r"(\b\w+)'re\b", re.IGNORECASE), r"\1 are"),
    (re.compile(r"(\b\w+)'ve\b", re.IGNORECASE), r"\1 have"),
    (re.compile(r"(\b\w+)'ll\b", re.IGNORECASE), r"\1 will"),
    (re.compile(r"(\b\w+)'m\b", re.IGNORECASE), r"\1 am"),
    (re.compile(r"(\b\w+)'d\b", re.IGNORECASE), r"\1 would"),
    (
        re.compile(
            r"(\bit|he|she|that|there|what|where|who)'s\b", re.IGNORECASE
        ),
        r"\1 is",
    ),
]


def normalize_text(text: str) -> str:
    """Aplica expansão de contrações e une números às suas unidades de medida (sem espaço)."""
    for pattern, replacement in CONTRACTIONS:
        text = pattern.sub(replacement, text)

    # Remove o espaço entre o número e a unidade de medida (ex: '10 mg' -> '10mg')
    unit_pattern = re.compile(
        rf"(\b\d+(?:\.\d+)?)\s*({UNITS_REGEX})\b", re.IGNORECASE
    )
    text = unit_pattern.sub(r"\1\2", text)
    return text


def step_1_normalize():
    """Lê Dados/cases.csv, ignora o cabeçalho original e gera Dados/casesNormalizado.csv."""
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(CASES_FILE, mode="r", encoding="utf-8") as infile:
        reader = csv.reader(infile)
        header = next(reader)

        rows = []
        for row in reader:
            if not row:
                continue
            article_id, age, case_id, case_text, gender = row
            normalized_text = normalize_text(case_text)
            rows.append([article_id, age, case_id, normalized_text, gender])

    with open(
        NORMALIZED_FILE, mode="w", encoding="utf-8", newline=""
    ) as outfile:
        writer = csv.writer(outfile)
        writer.writerow(header)
        writer.writerows(rows)


def load_dictionary() -> dict:
    """Carrega o dicionário garantindo chaves em letras minúsculas."""
    dict_pos = {}
    if not DICT_FILE.exists():
        return dict_pos

    with open(DICT_FILE, mode="r", encoding="utf-8") as infile:
        reader = csv.reader(infile)
        next(reader, None)
        for row in reader:
            if len(row) >= 2:
                word, pos = row[0].strip().lower(), row[1].strip()
                dict_pos[word] = pos
    return dict_pos


def step_2_classify_pos():
    """Gera Dados/partOfSpeech.csv com apenas uma linha de tags POS por caso."""
    dict_pos = load_dictionary()

    exam_result_pattern = re.compile(
        rf"^\d+(?:\.\d+)?{UNITS_REGEX}$", re.IGNORECASE
    )
    number_pattern = re.compile(r"^\d+(?:\.\d+)?$")
    token_extractor = re.compile(
        rf"\b\d+(?:\.\d+)?{UNITS_REGEX}\b|\b\w+\b", re.IGNORECASE
    )

    pos_output = []

    with open(NORMALIZED_FILE, mode="r", encoding="utf-8") as infile:
        reader = csv.reader(infile)
        next(reader)

        for row in reader:
            if not row:
                continue
            article_id, _, case_id, case_text, _ = row
            tokens = token_extractor.findall(case_text)

            case_pos_list = []
            for token in tokens:
                token_clean = token.strip()

                if exam_result_pattern.match(token_clean):
                    pos = "ExamResult"
                elif number_pattern.match(token_clean):
                    pos = "Number"
                else:
                    word_lower = token_clean.lower()
                    pos = dict_pos.get(word_lower, "Medico")

                case_pos_list.append(pos)

            # Salva uma única linha por caso contendo a sequência de POS separada por espaço
            pos_output.append([article_id, case_id, " ".join(case_pos_list)])

    with open(POS_FILE, mode="w", encoding="utf-8", newline="") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(["article_id", "case_id", "pos"])
        writer.writerows(pos_output)


if __name__ == "__main__":
    step_1_normalize()
    step_2_classify_pos()
    print("Processamento concluído com sucesso!")