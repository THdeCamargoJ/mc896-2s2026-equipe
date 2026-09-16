from src.preprocessing import (
    normalize_text,
    tokenize,
    remove_stopwords,
    preprocess_text,
)


def test_normalize_text():
    text = "  Patient  has\nEPIGASTRIC   Pain.  "

    result = normalize_text(text)

    assert result == "patient has epigastric pain."


def test_tokenize_clinical_values():
    text = (
        "Lipase was 850 U/L, CRP was 96 mg/L, "
        "treatment lasted 5-day and lesion measured 4 cm."
    )

    tokens = tokenize(text.lower())

    assert "850" in tokens
    assert "u/l" in tokens
    assert "96" in tokens
    assert "mg/l" in tokens
    assert "5-day" in tokens
    assert "4" in tokens
    assert "cm" in tokens


def test_stopword_removal_keeps_clinical_information():
    tokens = [
        "the",
        "patient",
        "had",
        "850",
        "u/l",
        "elevated",
        "lipase",
    ]

    result = remove_stopwords(tokens)

    assert "the" not in result
    assert "had" not in result

    assert "850" in result
    assert "u/l" in result
    assert "lipase" in result


def test_original_text_is_preserved():
    original = (
        "The patient had Lipase of 850 U/L "
        "and a 4 cm pseudocyst."
    )

    result = preprocess_text(original)

    assert result.original == original


def test_preprocess_pipeline():
    original = "The patient had 850 U/L lipase."

    result = preprocess_text(original)

    assert result.original == original
    assert result.normalized == "the patient had 850 u/l lipase."

    assert "850" in result.tokens
    assert "u/l" in result.tokens

    assert "the" not in result.retrieval_tokens
    assert "patient" in result.retrieval_tokens
    assert "850" in result.retrieval_tokens
    assert "u/l" in result.retrieval_tokens
    assert "lipase" in result.retrieval_tokens