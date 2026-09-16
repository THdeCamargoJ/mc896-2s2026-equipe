import csv
from pathlib import Path

from src.vocab.vocabulary import VocabularyEntry
from src.graph.schema import NodeType


def load_vocabulary(path: str | Path) -> list[VocabularyEntry]:
    """
    Carrega um vocabulário CSV.

    Formato esperado:

        term,aliases,type,source,code

    Onde aliases são separados por '|'.

    O campo `type` é validado contra `graph.schema.NodeType`: qualquer
    valor que não corresponda a um tipo de nó existente faz com que o
    carregamento falhe imediatamente, em vez de gerar uma entrada com
    um tipo inválido/inconsistente que só seria percebida mais tarde,
    na construção do grafo.
    """

    path = Path(path)

    entries = []

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            aliases = tuple(
                alias.strip()
                for alias in row["aliases"].split("|")
                if alias.strip()
            )

            raw_type = row["type"].strip()

            try:
                NodeType(raw_type)
            except ValueError as error:
                raise ValueError(
                    f"Tipo inválido '{raw_type}' para o termo "
                    f"'{row['term'].strip()}' em {path}. "
                    f"Tipos válidos: {[t.value for t in NodeType]}."
                ) from error

            entries.append(
                VocabularyEntry(
                    term=row["term"].strip(),
                    aliases=aliases,
                    type=raw_type,
                    source=row.get("source", "manual").strip(),
                    code=row.get("code", "").strip(),
                )
            )

    return entries