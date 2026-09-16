from pathlib import Path

from src.extraction import Entity, extract_entities
from src.preprocessing import load_cases
from src.vocab import load_vocabulary


VOCABULARY_DIR = Path("vocabularies")
SAMPLE_CASES_PATH = Path("sample/cases.csv")

# Vocabulários relevantes para extração de entidades "core" (Disease,
# Symptom, Exam, Treatment/Medication, AnatomicalSite), conforme a issue.
# Unit, Interpretation, Status e Course ficam de fora aqui: são atributos
# de outras entidades, não entidades clínicas em si.
ENTITY_VOCAB_FILES = [
    "diseases.csv",
    "symptoms.csv",
    "exams.csv",
    "treatments.csv",
    "medications.csv",
    "anatomical_sites.csv",
]


def load_entity_vocabulary():
    vocabulary = []

    for filename in ENTITY_VOCAB_FILES:
        vocabulary.extend(load_vocabulary(VOCABULARY_DIR / filename))

    return vocabulary


def test_extract_entities_simple_text():
    """Testa o dictionary matching básico em uma frase curta."""

    vocabulary = load_entity_vocabulary()

    text = (
        "The patient presented with abdominal pain and nausea. "
        "A CT scan of the abdomen was performed, showing a pancreatic mass. "
        "She was treated with intravenous fluids."
    )

    entities = extract_entities(text, vocabulary)

    by_label = {entity.label: entity for entity in entities}

    assert "abdominal pain" in by_label
    assert by_label["abdominal pain"].type == "Symptom"

    assert "nausea" in by_label
    assert by_label["nausea"].type == "Symptom"

    # "CT scan" é um alias de "computed tomography".
    assert "computed tomography" in by_label
    assert by_label["computed tomography"].type == "Exam"
    assert "CT scan" in by_label["computed tomography"].surface_forms

    assert "intravenous fluids" in by_label
    assert by_label["intravenous fluids"].type == "Treatment"

    assert "abdomen" in by_label
    assert by_label["abdomen"].type == "AnatomicalSite"


def test_extract_entities_deduplicates_repeated_terms():
    """
    Testa que menções repetidas do mesmo termo geram uma única entidade,
    mas todas as posições são mantidas.
    """

    vocabulary = load_entity_vocabulary()

    text = "Nausea was present. Later, the nausea worsened."

    entities = extract_entities(text, vocabulary)

    nausea_entities = [e for e in entities if e.label == "nausea"]

    assert len(nausea_entities) == 1
    assert nausea_entities[0].count == 2
    assert len(nausea_entities[0].positions) == 2


def test_extract_entities_normalizes_aliases_to_canonical_label():
    """Testa que diferentes aliases do mesmo conceito viram um único label."""

    vocabulary = load_entity_vocabulary()

    text = "CEA was elevated. The carcinoembryonic antigen level was high."

    entities = extract_entities(text, vocabulary)

    cea_entities = [e for e in entities if e.label == "carcinoembryonic antigen"]

    assert len(cea_entities) == 1
    assert cea_entities[0].count == 2
    assert set(cea_entities[0].surface_forms) == {
        "CEA",
        "carcinoembryonic antigen",
    }


def test_extract_entities_every_entity_has_a_type():
    """Garante que toda entidade extraída possui um tipo vindo do vocabulário."""

    vocabulary = load_entity_vocabulary()

    text = (
        "The patient underwent an endoscopy and was diagnosed with "
        "acute pancreatitis. She received analgesia and hydroxychloroquine."
    )

    entities = extract_entities(text, vocabulary)

    assert len(entities) > 0

    for entity in entities:
        assert entity.type, f"Entidade '{entity.label}' sem tipo."
        assert entity.positions, f"Entidade '{entity.label}' sem posições."


def test_extract_entities_on_a_real_case():
    """
    Critério de aceite: pelo menos um caso completo do dataset é
    convertido em entidades.
    """

    vocabulary = load_entity_vocabulary()
    cases = load_cases(SAMPLE_CASES_PATH)

    case = cases[0]
    entities = extract_entities(case["case_text"], vocabulary)

    assert len(entities) > 0

    # Tipos esperados presentes no primeiro caso da amostra (cisto
    # gástrico/pancreático): pelo menos Symptom, Exam e AnatomicalSite.
    types_found = {entity.type for entity in entities}
    assert "Symptom" in types_found
    assert "Exam" in types_found
    assert "AnatomicalSite" in types_found

    for entity in entities:
        assert isinstance(entity, Entity)
        assert entity.label
        assert entity.type
        assert entity.positions


def test_extract_entities_on_all_sample_cases_runs_without_error():
    """
    Garante que o pipeline roda sobre todo o dataset de amostra sem
    lançar exceções, mesmo em casos fora do escopo clínico coberto pelos
    vocabulários (ex.: relatos sem terminologia clínica reconhecida).
    """

    vocabulary = load_entity_vocabulary()
    cases = load_cases(SAMPLE_CASES_PATH)

    assert len(cases) > 0

    cases_with_entities = 0

    for case in cases:
        entities = extract_entities(case["case_text"], vocabulary)

        for entity in entities:
            assert entity.type
            assert entity.label
            assert entity.positions

        if entities:
            cases_with_entities += 1

    # A maioria dos casos deve gerar pelo menos uma entidade.
    assert cases_with_entities / len(cases) > 0.5
