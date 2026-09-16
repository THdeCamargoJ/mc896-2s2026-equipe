from src.Regex.measurement_adapter import extract_structured_measurements
from src.extraction.entities import Entity


def test_extracts_values_reference_range_and_case_insensitive_interpretation():
    text = "Lipase was Elevated at 850 U/L (reference range 10-140 U/L)."
    lipase = Entity(label="lipase", type="Exam", positions=[(0, 6)])

    results = extract_structured_measurements(text, [lipase])

    value = next(result for result in results if result.text == "850 U/L")
    reference_range = next(
        result
        for result in results
        if result.reference_range is not None
    )
    interpretation = next(
        result
        for result in results
        if result.interpretation == "elevated"
    )

    assert value.value == "850"
    assert value.unit == "U/L"
    assert value.entity == lipase
    assert reference_range.reference_range.low == "10"
    assert reference_range.reference_range.high == "140"
    assert reference_range.unit == "U/L"
    assert interpretation.entity == lipase


def test_extracts_decimal_size_and_duration():
    text = "CRP was 12.5 mg/L. The lesion measured 4 cm. Symptoms lasted 5 days."

    results = extract_structured_measurements(text, [])
    values = {
        (result.value, result.unit)
        for result in results
        if result.value is not None
    }

    assert ("12.5", "mg/L") in values
    assert ("4", "cm") in values
    assert ("5", "days") in values


def test_does_not_associate_entity_from_another_sentence():
    text = "Lipase was requested. The result was 850 U/L."
    lipase = Entity(label="lipase", type="Exam", positions=[(0, 6)])

    results = extract_structured_measurements(text, [lipase])
    value = next(result for result in results if result.text == "850 U/L")

    assert value.entity is None


def test_associates_measurements_with_other_measurable_entity_types():
    examples = [
        ("Ibuprofen 400 mg was prescribed.", "ibuprofen", "Medication"),
        ("Radiotherapy 50 Gy was delivered.", "radiotherapy", "Treatment"),
        ("Abdominal pain lasted 5 days.", "abdominal pain", "Symptom"),
        ("Hypertension persisted for 10 years.", "hypertension", "Diagnosis"),
        ("The liver measured 18 cm.", "liver", "AnatomicalSite"),
    ]

    for text, label, entity_type in examples:
        start = text.lower().index(label)
        entity = Entity(
            label=label,
            type=entity_type,
            positions=[(start, start + len(label))],
        )

        results = extract_structured_measurements(text, [entity])
        numeric_result = next(result for result in results if result.value)

        assert numeric_result.entity == entity


def test_does_not_treat_arbitrary_number_near_treatment_as_a_dose():
    text = "Surgery in 2019 was successful."
    surgery = Entity(label="surgery", type="Treatment", positions=[(0, 7)])

    results = extract_structured_measurements(text, [surgery])

    assert all(result.entity is None for result in results)


def test_text_without_measurement_returns_empty_list():
    assert extract_structured_measurements("The patient recovered.", []) == []
