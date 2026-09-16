from pathlib import Path

from src.vocab import VocabularyEntry, load_vocabulary


VOCABULARY_DIR = Path("vocabularies")


def test_vocabulary_entry():
    """Testa a criação e o comportamento de uma entrada de vocabulário."""

    entry = VocabularyEntry(
        term="C-reactive protein",
        aliases=("CRP", "C reactive protein"),
        type="Exam",
    )

    assert entry.term == "C-reactive protein"
    assert entry.type == "Exam"

    assert "CRP" in entry.aliases
    assert "C reactive protein" in entry.aliases

    # O termo canônico também deve aparecer em all_terms.
    assert "C-reactive protein" in entry.all_terms


def test_load_vocabulary():
    """Testa o carregamento de um vocabulário específico."""

    path = VOCABULARY_DIR / "symptoms.csv"

    entries = load_vocabulary(path)

    assert len(entries) > 0

    # Verifica se conseguimos encontrar um conceito esperado.
    epigastric_pain = next(
        entry
        for entry in entries
        if entry.term == "epigastric pain"
    )

    assert epigastric_pain.type == "Symptom"
    assert "epigastric discomfort" in epigastric_pain.aliases


def test_all_vocabularies():
    """
    Verifica todos os arquivos CSV da pasta vocabularies.

    Garante que:
    - existem vocabulários;
    - cada arquivo pode ser carregado;
    - cada vocabulário possui entradas;
    - todas as entradas possuem termo e tipo.
    """

    files = sorted(VOCABULARY_DIR.glob("*.csv"))

    assert len(files) > 0, "Nenhum arquivo de vocabulário encontrado."

    for path in files:
        entries = load_vocabulary(path)

        assert len(entries) > 0, (
            f"O vocabulário {path.name} está vazio."
        )

        for entry in entries:
            assert entry.term, (
                f"Entrada sem termo em {path.name}."
            )

            assert entry.type, (
                f"Entrada sem tipo em {path.name}: {entry.term}"
            )


def test_all_vocabulary_aliases():
    """
    Verifica que aliases não estão vazios ou contendo strings vazias.
    """

    files = sorted(VOCABULARY_DIR.glob("*.csv"))

    for path in files:
        entries = load_vocabulary(path)

        for entry in entries:
            for alias in entry.aliases:
                assert alias.strip() != "", (
                    f"Alias vazio em {path.name}: {entry.term}"
                )